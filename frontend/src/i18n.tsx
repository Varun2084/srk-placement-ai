import { createContext, useContext, useState, type ReactNode } from "react";

type Lang = "en" | "hi";
const DICT: Record<string, { en: string; hi: string }> = {
  myProfile: { en: "My profile", hi: "मेरी प्रोफ़ाइल" },
  drives: { en: "Placement drives", hi: "प्लेसमेंट ड्राइव" },
  readiness: { en: "Readiness report", hi: "तैयारी रिपोर्ट" },
  uploadResume: { en: "Upload resume (PDF, DOCX or TXT, max 5 MB)", hi: "रिज़्यूमे अपलोड करें (PDF, DOCX या TXT, अधिकतम 5 MB)" },
  consentTitle: { en: "Privacy notice", hi: "गोपनीयता सूचना" },
  consentText: {
    en: "The placement cell will use your resume and academic record only to prepare you for placements and to match you with employer drives. AI helps sort and explain; placement staff make every decision. Your profile is shared with an employer only if you agree for that employer. You can view and correct your data, and withdraw consent, at any time. Data is deleted 12 months after you graduate.",
    hi: "प्लेसमेंट सेल आपके रिज़्यूमे और शैक्षणिक रिकॉर्ड का उपयोग केवल प्लेसमेंट की तैयारी और कंपनी ड्राइव से मिलान के लिए करेगा। AI केवल छाँटने और समझाने में मदद करता है; हर निर्णय प्लेसमेंट स्टाफ लेता है। आपकी प्रोफ़ाइल किसी कंपनी को तभी भेजी जाएगी जब आप उस कंपनी के लिए अनुमति देंगे। आप कभी भी अपना डेटा देख, सुधार और अनुमति वापस ले सकते हैं। स्नातक होने के 12 महीने बाद डेटा हटा दिया जाता है।",
  },
  accept: { en: "I agree", hi: "मैं सहमत हूँ" },
  withdraw: { en: "Withdraw consent", hi: "अनुमति वापस लें" },
  apply: { en: "Apply", hi: "आवेदन करें" },
  shareWith: { en: "Allow sharing my profile with this employer", hi: "इस कंपनी के साथ मेरी प्रोफ़ाइल साझा करने की अनुमति दें" },
  gaps: { en: "What to add next", hi: "आगे क्या जोड़ें" },
  extracted: { en: "What we read from your resume — correct anything that is wrong", hi: "आपके रिज़्यूमे से पढ़ी गई जानकारी — गलत हो तो सुधारें" },
  logout: { en: "Log out", hi: "लॉग आउट" },
};

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({ lang: "en", setLang: () => {} });

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("en");
  return <Ctx.Provider value={{ lang, setLang }}>{children}</Ctx.Provider>;
}

export function useT() {
  const { lang, setLang } = useContext(Ctx);
  const t = (k: keyof typeof DICT | string) => DICT[k]?.[lang] ?? k;
  return { t, lang, setLang };
}
