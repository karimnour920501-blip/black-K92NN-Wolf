using System.Security.Cryptography;
using System.Text;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);
var connectionString = builder.Configuration["BLACKWOLF_DB"] ?? throw new InvalidOperationException("BLACKWOLF_DB required");
var adminToken = builder.Configuration["BLACKWOLF_ADMIN_TOKEN"] ?? throw new InvalidOperationException("BLACKWOLF_ADMIN_TOKEN required");
if (Encoding.UTF8.GetByteCount(adminToken) < 32) throw new InvalidOperationException("Admin token must be at least 32 bytes");
var app = builder.Build();

bool IsAuthorized(HttpRequest request)
{
    if (!request.Headers.TryGetValue("X-Admin-Token", out var provided)) return false;
    var left = Encoding.UTF8.GetBytes(provided.ToString());
    var right = Encoding.UTF8.GetBytes(adminToken);
    return left.Length == right.Length && CryptographicOperations.FixedTimeEquals(left, right);
}
app.MapGet("/health", () => Results.Ok(new { status = "alive" }));
app.MapGet("/ready", async () =>
{
    try
    {
        await using var conn = new NpgsqlConnection(connectionString);
        await conn.OpenAsync();
        await using var cmd = new NpgsqlCommand("SELECT 1", conn);
        await cmd.ExecuteScalarAsync();
        return Results.Ok(new { status = "ready" });
    }
    catch { return Results.Json(new { status = "unavailable" }, statusCode: 503); }
});
app.MapGet("/api/projects", async (HttpRequest request) =>
{
    if (!IsAuthorized(request)) return Results.Unauthorized();
    await using var conn = new NpgsqlConnection(connectionString);
    await conn.OpenAsync();
    await using var cmd = new NpgsqlCommand("SELECT id, name, created_at FROM projects ORDER BY created_at DESC", conn);
    await using var reader = await cmd.ExecuteReaderAsync();
    var projects = new List<object>();
    while (await reader.ReadAsync())
        projects.Add(new { id = reader.GetGuid(0), name = reader.GetString(1), created_at = reader.GetDateTime(2) });
    return Results.Ok(projects);
});
app.MapPost("/api/projects", async (HttpRequest request, ProjectInput input) =>
{
    if (!IsAuthorized(request)) return Results.Unauthorized();
    if (string.IsNullOrWhiteSpace(input.Name) || input.Name.Length > 120)
        return Results.BadRequest(new { error = "invalid_name" });
    await using var conn = new NpgsqlConnection(connectionString);
    await conn.OpenAsync();
    await using var tx = await conn.BeginTransactionAsync();
    var id = Guid.NewGuid();
    await using (var cmd = new NpgsqlCommand("INSERT INTO projects(id,name) VALUES (@id,@name)", conn, tx))
    {
        cmd.Parameters.AddWithValue("id", id);
        cmd.Parameters.AddWithValue("name", input.Name.Trim());
        await cmd.ExecuteNonQueryAsync();
    }
    await using (var cmd = new NpgsqlCommand("INSERT INTO audit_log(action,target) VALUES ('project.created',@target)", conn, tx))
    {
        cmd.Parameters.AddWithValue("target", id.ToString());
        await cmd.ExecuteNonQueryAsync();
    }
    await tx.CommitAsync();
    return Results.Created($"/api/projects/{id}", new { id, name = input.Name.Trim() });
});
app.MapGet("/api/servers", async (HttpRequest request) =>
{
    if (!IsAuthorized(request)) return Results.Unauthorized();
    await using var conn = new NpgsqlConnection(connectionString);
    await conn.OpenAsync();
    await using var cmd = new NpgsqlCommand("SELECT id,project_id,label,hostname,ssh_port FROM servers ORDER BY created_at DESC", conn);
    await using var reader = await cmd.ExecuteReaderAsync();
    var servers = new List<object>();
    while (await reader.ReadAsync())
        servers.Add(new { id = reader.GetGuid(0), project_id = reader.GetGuid(1), label = reader.GetString(2), hostname = reader.GetString(3), ssh_port = reader.GetInt32(4) });
    return Results.Ok(servers);
});
app.MapGet("/api/audit", async (HttpRequest request) =>
{
    if (!IsAuthorized(request)) return Results.Unauthorized();
    await using var conn = new NpgsqlConnection(connectionString);
    await conn.OpenAsync();
    await using var cmd = new NpgsqlCommand("SELECT id,action,target,created_at FROM audit_log ORDER BY id DESC LIMIT 100", conn);
    await using var reader = await cmd.ExecuteReaderAsync();
    var entries = new List<object>();
    while (await reader.ReadAsync())
        entries.Add(new { id = reader.GetInt64(0), action = reader.GetString(1), target = reader.GetString(2), created_at = reader.GetDateTime(3) });
    return Results.Ok(entries);
});

static string HashKey(string key) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(key))).ToLowerInvariant();

async Task<Guid?> TenantFromRequest(HttpRequest request)
{
    if (!request.Headers.TryGetValue("X-Tenant-Key", out var key) || key.Count != 1 || key.ToString().Length < 32) return null;
    await using var conn = new NpgsqlConnection(connectionString);
    await conn.OpenAsync();
    await using var cmd = new NpgsqlCommand("SELECT id FROM tenants WHERE api_key_hash=@hash", conn);
    cmd.Parameters.AddWithValue("hash", HashKey(key.ToString()));
    var result = await cmd.ExecuteScalarAsync();
    return result is Guid id ? id : null;
}
// Restricted to bootstrap admin; caller provides a strong tenant key. Key is never returned or stored in plaintext.
app.MapPost("/admin/tenants", async (HttpRequest request, TenantInput input) =>
{
    if (!IsAuthorized(request)) return Results.Unauthorized();
    if (string.IsNullOrWhiteSpace(input.Name) || input.Name.Length > 120 || input.ApiKey is null || Encoding.UTF8.GetByteCount(input.ApiKey) < 32)
        return Results.BadRequest(new { error = "invalid_tenant" });
    var id = Guid.NewGuid();
    await using var conn = new NpgsqlConnection(connectionString);
    await conn.OpenAsync();
    await using var cmd = new NpgsqlCommand("INSERT INTO tenants(id,name,api_key_hash) VALUES (@id,@name,@hash)", conn);
    cmd.Parameters.AddWithValue("id", id);
    cmd.Parameters.AddWithValue("name", input.Name.Trim());
    cmd.Parameters.AddWithValue("hash", HashKey(input.ApiKey));
    await cmd.ExecuteNonQueryAsync();
    return Results.Created($"/admin/tenants/{id}", new { id, name = input.Name.Trim() });
});
app.MapGet("/api/v1/tenant/projects", async (HttpRequest request) =>
{
    var tenantId = await TenantFromRequest(request);
    if (tenantId is null) return Results.Unauthorized();
    await using var conn = new NpgsqlConnection(connectionString);
    await conn.OpenAsync();
    await using var cmd = new NpgsqlCommand("SELECT id,name,created_at FROM tenant_projects WHERE tenant_id=@tenant ORDER BY created_at DESC", conn);
    cmd.Parameters.AddWithValue("tenant", tenantId.Value);
    await using var reader = await cmd.ExecuteReaderAsync();
    var projects = new List<object>();
    while (await reader.ReadAsync())
        projects.Add(new { id = reader.GetGuid(0), name = reader.GetString(1), created_at = reader.GetDateTime(2) });
    return Results.Ok(projects);
});
app.MapPost("/api/v1/tenant/projects", async (HttpRequest request, ProjectInput input) =>
{
    var tenantId = await TenantFromRequest(request);
    if (tenantId is null) return Results.Unauthorized();
    if (string.IsNullOrWhiteSpace(input.Name) || input.Name.Length > 120)
        return Results.BadRequest(new { error = "invalid_name" });
    var id = Guid.NewGuid();
    await using var conn = new NpgsqlConnection(connectionString);
    await conn.OpenAsync();
    await using var cmd = new NpgsqlCommand("INSERT INTO tenant_projects(id,tenant_id,name) VALUES (@id,@tenant,@name)", conn);
    cmd.Parameters.AddWithValue("id", id);
    cmd.Parameters.AddWithValue("tenant", tenantId.Value);
    cmd.Parameters.AddWithValue("name", input.Name.Trim());
    await cmd.ExecuteNonQueryAsync();
    return Results.Created($"/api/v1/tenant/projects/{id}", new { id, name = input.Name.Trim() });
});
app.Run();
record ProjectInput(string Name);
record TenantInput(string Name, string ApiKey);
