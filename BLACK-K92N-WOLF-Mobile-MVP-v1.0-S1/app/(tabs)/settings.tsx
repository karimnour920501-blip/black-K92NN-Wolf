import React from 'react';
import { Screen } from '../../src/components/Screen';
import { InfoCard } from '../../src/components/InfoCard';
export default function Settings() { return <Screen title="الإعدادات" subtitle="التفضيلات وإدارة الحساب في المراحل التالية"><InfoCard label="الإصدار" value="1.0.0-S1"/><InfoCard label="الوضع" value="معاينة غير مصادقة" note="لا تخزن هذه النسخة رموز جلسات أو بيانات خاصة"/></Screen>; }
