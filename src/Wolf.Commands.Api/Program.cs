using static TenantGuard;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);
var issuer = builder.Configuration["JWT_ISSUER"] ?? throw new InvalidOperationException("JWT_ISSUER required");
var audience = builder.Configuration["JWT_AUDIENCE"] ?? throw new InvalidOperationException("JWT_AUDIENCE required");
var key = builder.Configuration["JWT_SIGNING_KEY"] ?? throw new InvalidOperationException("JWT_SIGNING_KEY required");
if (Encoding.UTF8.GetByteCount(key) < 32) throw new InvalidOperationException("JWT_SIGNING_KEY must be >=32 bytes");
var connectionString = builder.Configuration["DATABASE_URL"] ?? throw new InvalidOperationException("DATABASE_URL required");
builder.Services.AddSingleton(NpgsqlDataSource.Create(connectionString));
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(o => {
    o.MapInboundClaims = false;
    o.TokenValidationParameters = new TokenValidationParameters {
        ValidateIssuer = true, ValidIssuer = issuer, ValidateAudience = true, ValidAudience = audience,
        ValidateIssuerSigningKey = true, IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(key)),
        ValidateLifetime = true, ClockSkew = TimeSpan.FromSeconds(30), RequireSignedTokens = true,
        ValidAlgorithms = new[] { SecurityAlgorithms.HmacSha256 }
    };
});
builder.Services.AddAuthorization();
var path = Path.Combine(AppContext.BaseDirectory, "commands.json");
using var doc = JsonDocument.Parse(File.ReadAllText(path));
var commands = doc.RootElement.GetProperty("commands").EnumerateArray()
    .Select(x => new Command(x.GetProperty("command").GetString()!, x.GetProperty("description").GetString()!))
    .ToDictionary(x => x.Name, StringComparer.OrdinalIgnoreCase);
if (commands.Count != 100) throw new InvalidOperationException("Expected 100 unique commands");
var app = builder.Build();
app.UseAuthentication(); app.UseAuthorization();
app.MapGet("/health/live", () => Results.Ok(new { status = "alive" }));
app.MapGet("/health/ready", async (NpgsqlDataSource db, CancellationToken ct) => {
    try { await using var c = await db.OpenConnectionAsync(ct);
        await using var cmd = new NpgsqlCommand("SELECT 1", c);
        await cmd.ExecuteScalarAsync(ct);
        return Results.Ok(new { status = "ready" });
    } catch { return Results.StatusCode(503); }
});
app.MapGet("/api/v1/projects", async (ClaimsPrincipal user, NpgsqlDataSource db, CancellationToken ct) => {
    if (!TryTenant(user, out var tenant)) return Results.Forbid();
    await using var conn = await db.OpenConnectionAsync(ct);
    await using var tx = await conn.BeginTransactionAsync(ct);
    await SetTenant(conn, tx, tenant, ct);
    await using var cmd = new NpgsqlCommand("SELECT id, name, created_at FROM workspace_projects ORDER BY created_at DESC LIMIT 100", conn, tx);
    var rows = new List<object>();
    await using (var reader = await cmd.ExecuteReaderAsync(ct)) {
        while (await reader.ReadAsync(ct)) rows.Add(new { id = reader.GetGuid(0), name = reader.GetString(1), createdAt = reader.GetDateTime(2) });
    }
    await tx.CommitAsync(ct);
    return Results.Ok(rows);
}).RequireAuthorization();
app.MapPost("/api/v1/projects", async (CreateProjectRequest req, ClaimsPrincipal user, NpgsqlDataSource db, CancellationToken ct) => {
    if (!TryTenant(user, out var tenant) || !CanWrite(user)) return Results.Forbid();
    if (string.IsNullOrWhiteSpace(req.Name) || req.Name.Length > 120) return Results.BadRequest(new { error = "INVALID_NAME" });
    await using var conn = await db.OpenConnectionAsync(ct);
    await using var tx = await conn.BeginTransactionAsync(ct);
    await SetTenant(conn, tx, tenant, ct);
    var id = Guid.NewGuid();
    await using var cmd = new NpgsqlCommand("INSERT INTO workspace_projects (id,tenant_id,name) VALUES (@id,@tenant,@name)", conn, tx);
    cmd.Parameters.AddWithValue("id", id); cmd.Parameters.AddWithValue("tenant", tenant); cmd.Parameters.AddWithValue("name", req.Name.Trim());
    await cmd.ExecuteNonQueryAsync(ct);
    await tx.CommitAsync(ct);
    return Results.Created($"/api/v1/projects/{id}", new { id, name = req.Name.Trim() });
}).RequireAuthorization();
app.MapGet("/api/v1/commands", (ClaimsPrincipal user) => Results.Ok(commands.Values.OrderBy(c => c.Name)))
    .RequireAuthorization();
app.MapPost("/api/v1/execute", async (ExecuteRequest req, ClaimsPrincipal user, NpgsqlDataSource db, CancellationToken ct) => {
    var tenant = user.FindFirst("tenant_id")?.Value;
    var subject = user.FindFirst("sub")?.Value;
    var role = user.FindFirst("role")?.Value;
    if (string.IsNullOrWhiteSpace(tenant) || string.IsNullOrWhiteSpace(subject)) return Results.Forbid();
    if (!Guid.TryParse(tenant, out var tenantId)) return Results.Forbid();
    if (role is not ("operator" or "admin")) return Results.Forbid();
    if (string.IsNullOrWhiteSpace(req.Command) || req.Command.Length > 2048) return Results.BadRequest(new { error = "INVALID_COMMAND" });
    var match = Regex.Match(req.Command, @"^(/[a-z][a-z0-9-]*)(?:\s+(.*))?$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    if (!match.Success) return Results.BadRequest(new { error = "INVALID_SYNTAX" });
    var name = match.Groups[1].Value;
    if (!commands.ContainsKey(name)) return Results.NotFound(new { error = "UNKNOWN_COMMAND" });
    if (!name.Equals("/design-brief", StringComparison.OrdinalIgnoreCase)) return Results.Conflict(new { error = "NO_HANDLER" });
    var input = match.Groups[2].Value.Trim();
    if (input.Length is < 1 or > 1000) return Results.BadRequest(new { error = "INPUT_REQUIRED_OR_TOO_LONG" });
    var result = JsonSerializer.Serialize(new { title = "Design brief draft", objective = input, status = "draft", warning = "Template only; not an approved design" });
    var requestHash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(req.Command))).ToLowerInvariant();
    await using var conn = await db.OpenConnectionAsync(ct);
    await using var tx = await conn.BeginTransactionAsync(ct);
    await using (var scope = new NpgsqlCommand("SELECT set_config('app.tenant_id', @tenant, true)", conn, tx)) {
        scope.Parameters.AddWithValue("tenant", tenantId.ToString("D")); await scope.ExecuteNonQueryAsync(ct);
    }
    await using (var guard = new NpgsqlCommand("SELECT pg_advisory_xact_lock(hashtextextended(@tenant, 0))", conn, tx)) {
        guard.Parameters.AddWithValue("tenant", tenantId.ToString()); await guard.ExecuteNonQueryAsync(ct);
    }
    string prev = new string('0',64);
    await using (var last = new NpgsqlCommand("SELECT entry_hash FROM command_evidence WHERE tenant_id=@tenant ORDER BY sequence DESC LIMIT 1", conn, tx)) {
        last.Parameters.AddWithValue("tenant", tenantId);
        prev = (string?)await last.ExecuteScalarAsync(ct) ?? prev;
    }
    var resultHash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(result))).ToLowerInvariant();
    var payload = string.Join("|", tenantId.ToString("D"), subject, name.ToLowerInvariant(), requestHash, resultHash, prev);
    var entryHash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
    await using (var insert = new NpgsqlCommand("INSERT INTO command_evidence (tenant_id, actor_id, command_name, request_hash, result_hash, previous_hash, entry_hash) VALUES (@t,@a,@c,@r,@o,@p,@h)", conn, tx)) {
        insert.Parameters.AddWithValue("t", tenantId); insert.Parameters.AddWithValue("a", subject);
        insert.Parameters.AddWithValue("c", name.ToLowerInvariant()); insert.Parameters.AddWithValue("r", requestHash);
        insert.Parameters.AddWithValue("o", resultHash); insert.Parameters.AddWithValue("p", prev); insert.Parameters.AddWithValue("h", entryHash);
        await insert.ExecuteNonQueryAsync(ct);
    }
    await tx.CommitAsync(ct);
    return Results.Ok(new { command = name, result = JsonSerializer.Deserialize<JsonElement>(result), evidenceHash = entryHash });
}).RequireAuthorization();
app.Run();
public record Command(string Name, string Description);
public record ExecuteRequest(string Command);
public partial class Program { }
public record CreateProjectRequest(string Name);
public static class TenantGuard {
    public static bool TryTenant(ClaimsPrincipal user, out Guid tenant) =>
        Guid.TryParse(user.FindFirst("tenant_id")?.Value, out tenant);
    public static bool CanWrite(ClaimsPrincipal user) =>
        user.FindAll("role").Any(c => c.Value is "operator" or "admin");
    public static async Task SetTenant(NpgsqlConnection conn, NpgsqlTransaction tx, Guid tenant, CancellationToken ct) {
        await using var scope = new NpgsqlCommand("SELECT set_config('app.tenant_id', @tenant, true)", conn, tx);
        scope.Parameters.AddWithValue("tenant", tenant.ToString("D"));
        await scope.ExecuteNonQueryAsync(ct);
    }
}
