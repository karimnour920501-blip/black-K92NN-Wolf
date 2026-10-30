import React from 'react';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Screen } from '../src/components/Screen';
import { StatePanel } from '../src/components/StatePanel';
import { tokens } from '../src/design/tokens';
/** S1: deliberately no token/session restore. Never assume an authenticated user. */
export default function Splash() {
  return <Screen title="مرحبًا بك" subtitle="BLACK-K92N-WOLF · Mobile MVP v1.0">
    <StatePanel state="unauthorized" />
    <View style={styles.notice}><Text style={styles.noticeText}>وضع العرض التأسيسي S1: لم تُربط المصادقة بعد. لا تُعرض بيانات خاصة أو نتائج تشغيل حقيقية.</Text></View>
    <Pressable style={styles.button} accessibilityRole="button" onPress={() => router.replace('/(tabs)')}><Text style={styles.buttonText}>استعراض الواجهة التجريبية</Text></Pressable>
  </Screen>;
}
const styles = StyleSheet.create({ notice: { padding: 16, borderWidth: 1, borderColor: tokens.colors.border, borderRadius: 12 }, noticeText: { color: tokens.colors.muted, lineHeight: 24, textAlign: 'left' }, button: { backgroundColor: tokens.colors.gold, minHeight: tokens.touchTarget, borderRadius: 12, justifyContent: 'center', alignItems: 'center' }, buttonText: { color: tokens.colors.background, fontWeight: '800' } });
