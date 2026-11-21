// Fixed Bangla texts. The first group is copied word for word from SRS Appendix A
// (backend/app/domain/messages_bn.py); keep them identical. The second group is app-only UI text.

export const MSG = {
  ERROR: 'দুঃখিত, এখন একটু সমস্যা হচ্ছে। একটু পরে আবার চেষ্টা করুন অথবা ৩৩৩ নম্বরে ফোন করুন।',
  INVALID_PHONE: 'মোবাইল নম্বরটি সঠিক নয়। ০১ দিয়ে শুরু ১১ অঙ্কের নম্বর দিন।',
  DECISION_NOTE: 'চূড়ান্ত সিদ্ধান্ত সংশ্লিষ্ট অফিস নেবে।',
} as const

export const UI = {
  appName: 'এক কল',
  appNameEn: 'Ek Call',
  tagline: 'সরকারি সেবার তথ্য, বাংলায়, এক কলে।',
  startExplain:
    'বয়স্ক ভাতা, বিধবা ভাতা, এনআইডি সংশোধন, জন্ম নিবন্ধন, পাসপোর্টসহ ৮টি সরকারি সেবা নিয়ে প্রশ্ন করুন। উত্তর আসবে সরকারি কাগজ থেকে।',
  phoneLabel: 'আপনার মোবাইল নম্বর',
  phoneLabelEn: 'Your mobile number',
  phonePlaceholder: '০১XXXXXXXXX',
  start: 'শুরু করুন',
  startEn: 'Start',
  privacyNote: 'নম্বরটি শুধু আপনার আগের উত্তরগুলো দেখাতে ব্যবহার হয়।',
  inputPlaceholder: 'আপনার প্রশ্ন লিখুন…',
  send: 'পাঠান',
  sendEn: 'Send',
  examplesTitle: 'উদাহরণ প্রশ্ন',
  thinking: 'উত্তর খোঁজা হচ্ছে…',
  emptyChat: 'নিচে প্রশ্ন লিখুন অথবা একটি উদাহরণ বেছে নিন।',
  followUpLabel: 'একটি প্রশ্ন',
  fallbackLabel: 'নিশ্চিত তথ্য পাওয়া যায়নি',
  changeNumber: 'নম্বর বদলান',
  you: 'আপনি',
} as const
