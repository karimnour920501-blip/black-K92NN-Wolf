import React from 'react';
import { Screen } from '../../src/components/Screen';
import { InfoCard } from '../../src/components/InfoCard';
export default function Home() { return <Screen title="لوحة القيادة" subtitle="معاينة S1 دون اتصال بالخادم"><InfoCard label="حالة الربط" value="غير متصل" note="لا تُعرض بيانات تشغيلية مختلقة"/><InfoCard label="مكتبة الأوامر" value="100 تعريف" note="الكتالوج الأصلي؛ التنفيذ غير مفعل في S1"/><InfoCard label="المشاريع" value="—" note="سيُربط الخادم في Sprint لاحق"/></Screen>; }
