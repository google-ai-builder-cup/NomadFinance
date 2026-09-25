export interface DialCode {
  /** ISO 3166-1 alpha-2 code; shown instead of a translated country name. */
  country: string;
  dialCode: string;
}

// Host countries first (where workers hold a local SIM), then home countries.
export const PHONE_DIAL_CODES: readonly DialCode[] = [
  { country: "SG", dialCode: "+65" },
  { country: "MY", dialCode: "+60" },
  { country: "HK", dialCode: "+852" },
  { country: "JP", dialCode: "+81" },
  { country: "KR", dialCode: "+82" },
  { country: "AU", dialCode: "+61" },
  { country: "PH", dialCode: "+63" },
  { country: "IN", dialCode: "+91" },
  { country: "ID", dialCode: "+62" },
  { country: "NP", dialCode: "+977" },
  { country: "BD", dialCode: "+880" },
];
