import React from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { tokens } from '../../src/design/tokens';
export default function TabLayout() {
  return <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: tokens.colors.gold, tabBarInactiveTintColor: tokens.colors.muted, tabBarStyle: { backgroundColor: tokens.colors.surface, borderTopColor: tokens.colors.border, minHeight: 62 }, tabBarLabelStyle: { fontSize: 11 } }}>
    <Tabs.Screen name="home" options={{ title: 'الرئيسية', tabBarIcon: ({ color, size }) => <Ionicons name="grid-outline" color={color} size={size} /> }} />
    <Tabs.Screen name="projects" options={{ title: 'المشاريع', tabBarIcon: ({ color, size }) => <Ionicons name="folder-outline" color={color} size={size} /> }} />
    <Tabs.Screen name="commands" options={{ title: 'الأوامر', tabBarIcon: ({ color, size }) => <Ionicons name="terminal-outline" color={color} size={size} /> }} />
    <Tabs.Screen name="evidence" options={{ title: 'الأدلة', tabBarIcon: ({ color, size }) => <Ionicons name="shield-checkmark-outline" color={color} size={size} /> }} />
    <Tabs.Screen name="settings" options={{ title: 'الإعدادات', tabBarIcon: ({ color, size }) => <Ionicons name="settings-outline" color={color} size={size} /> }} />
  </Tabs>;
}
