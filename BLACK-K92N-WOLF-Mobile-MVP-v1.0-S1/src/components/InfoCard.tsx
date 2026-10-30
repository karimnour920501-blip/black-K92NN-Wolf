import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { tokens } from '../design/tokens';
export function InfoCard({ label, value, note }: { label: string; value: string; note?: string }) {
  return <View style={styles.card}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{value}</Text>{note ? <Text style={styles.note}>{note}</Text> : null}</View>;
}
const styles = StyleSheet.create({ card: { backgroundColor: tokens.colors.surface, borderRadius: tokens.radii.lg, borderWidth: 1, borderColor: tokens.colors.border, padding: 18, gap: 8 }, label: { color: tokens.colors.muted, fontSize: 13 }, value: { color: tokens.colors.text, fontSize: 21, fontWeight: '700' }, note: { color: tokens.colors.muted, fontSize: 12 } });
