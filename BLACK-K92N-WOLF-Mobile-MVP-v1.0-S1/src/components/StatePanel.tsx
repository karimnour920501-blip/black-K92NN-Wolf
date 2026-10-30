import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { tokens } from '../design/tokens';
import { describeState, type UiState } from '../domain/ui-state.mjs';
export function StatePanel({ state, onRetry }: { state: UiState; onRetry?: () => void }) {
  const info = describeState(state);
  return <View accessibilityRole="summary" style={styles.panel}>
    <Text style={styles.title}>{info.title}</Text><Text style={styles.detail}>{info.detail}</Text>
    {info.retry && onRetry ? <Pressable accessibilityRole="button" accessibilityLabel="إعادة المحاولة" onPress={onRetry} style={styles.button}><Text style={styles.buttonText}>إعادة المحاولة</Text></Pressable> : null}
  </View>;
}
const styles = StyleSheet.create({ panel: { backgroundColor: tokens.colors.surface, borderColor: tokens.colors.border, borderWidth: 1, borderRadius: tokens.radii.lg, padding: tokens.spacing[5], gap: 12 }, title: { color: tokens.colors.text, fontSize: 18, fontWeight: '700', textAlign: 'left' }, detail: { color: tokens.colors.muted, fontSize: 15, lineHeight: 23, textAlign: 'left' }, button: { backgroundColor: tokens.colors.gold, minHeight: tokens.touchTarget, borderRadius: tokens.radii.md, alignItems: 'center', justifyContent: 'center' }, buttonText: { color: tokens.colors.background, fontWeight: '700' } });
