/** Pure state mapping used by React Native and by dependency-free Node tests. */
export const UI_STATES = Object.freeze(['loading', 'empty', 'offline', 'unauthorized', 'forbidden', 'notFound', 'conflict', 'rateLimited', 'serverError']);
const messages = Object.freeze({
  loading: { title: 'جارٍ التحميل', detail: 'يرجى الانتظار حتى اكتمال الطلب.', retry: false },
  empty: { title: 'لا توجد بيانات', detail: 'لم تُرجع الخدمة أي عناصر بعد.', retry: false },
  offline: { title: 'لا يوجد اتصال', detail: 'تحقق من اتصال الإنترنت ثم حاول مجددًا.', retry: true },
  unauthorized: { title: 'انتهت الجلسة', detail: 'سجّل الدخول مجددًا للمتابعة.', retry: false },
  forbidden: { title: 'غير مصرح', detail: 'ليست لديك صلاحية تنفيذ هذه العملية.', retry: false },
  notFound: { title: 'العنصر غير موجود', detail: 'تعذر العثور على المورد المطلوب.', retry: false },
  conflict: { title: 'تعذر إتمام العملية', detail: 'حدث تعارض أو أن الأمر غير مدعوم.', retry: false },
  rateLimited: { title: 'طلبات كثيرة', detail: 'انتظر قبل إرسال طلب جديد.', retry: false },
  serverError: { title: 'خطأ في الخدمة', detail: 'تعذر إتمام الطلب حاليًا.', retry: true }
});
export function describeState(state) {
  if (!UI_STATES.includes(state)) throw new RangeError('Unknown UI state: ' + state);
  return messages[state];
}
export function classifyHttpStatus(status) {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'notFound';
  if (status === 409) return 'conflict';
  if (status === 429) return 'rateLimited';
  if (Number.isInteger(status) && status >= 500 && status <= 599) return 'serverError';
  return null;
}
export function canRetryAutomatically(method, status) {
  return (method === 'GET' || method === 'HEAD') && status >= 500 && status <= 599;
}
