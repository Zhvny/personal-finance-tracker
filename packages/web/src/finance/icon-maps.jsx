// ─── finance/icon-maps.jsx ────────────────────────────────────────────────────
// JSX icon component maps for categories, asset types, income types, payments.
// Kept in a .jsx file so Vite correctly parses the JSX syntax.

import {
  IconFood, IconTransport, IconHousing, IconEntertainment,
  IconHealth, IconShopping, IconEducation, IconOther, IconInvestment,
  IconStock, IconCrypto, IconGold,
  IconSalary, IconFreelance, IconSideHustle,
  IconCashPay, IconDebitCard, IconCreditCard,
  IconEWallet, IconBankTransfer, IconQRIS, IconWallet,
} from "../icons.jsx";

// ── Category icons ────────────────────────────────────────────────────────────
export const CAT_ICON = {
  "Food & Drink": (p = {}) => <IconFood          {...p} />,
  transport:     (p = {}) => <IconTransport     {...p} />,
  housing:       (p = {}) => <IconHousing       {...p} />,
  entertainment: (p = {}) => <IconEntertainment {...p} />,
  health:        (p = {}) => <IconHealth        {...p} />,
  shopping:      (p = {}) => <IconShopping      {...p} />,
  education:     (p = {}) => <IconEducation     {...p} />,
  investment:    (p = {}) => <IconInvestment    {...p} />,
  other:         (p = {}) => <IconOther         {...p} />,
};

export const CatIcon = ({ cat, size = 13, color }) =>
  CAT_ICON[cat]
    ? CAT_ICON[cat]({ size, color })
    : <IconOther size={size} color={color} />;

// ── Asset type icons ──────────────────────────────────────────────────────────
export const TYPE_ICON = {
  stock:  (p = {}) => <IconStock  {...p} />,
  crypto: (p = {}) => <IconCrypto {...p} />,
  gold:   (p = {}) => <IconGold   {...p} />,
};

// ── Income type icons ─────────────────────────────────────────────────────────
export const INC_ICON = {
  salary:        (p = {}) => <IconSalary     {...p} />,
  freelance:     (p = {}) => <IconFreelance  {...p} />,
  investment:    (p = {}) => <IconInvestment {...p} />,
  "side-hustle": (p = {}) => <IconSideHustle {...p} />,
  transfer:      (p = {}) => <IconBankTransfer {...p} />,
  other:         (p = {}) => <IconOther      {...p} />,
};

export const IncIcon = ({ type, size = 13, color }) =>
  INC_ICON[type]
    ? INC_ICON[type]({ size, color })
    : <IconOther size={size} color={color} />;

// ── Payment method icons ──────────────────────────────────────────────────────
export const PAY_META = {
  "cash":          { Icon: IconCashPay,      label: "Cash" },
  "debit-card":    { Icon: IconDebitCard,    label: "Debit Card" },
  "credit-card":   { Icon: IconCreditCard,   label: "Credit Card" },
  "e-wallet":      { Icon: IconEWallet,      label: "E-Wallet" },
  "bank-transfer": { Icon: IconBankTransfer, label: "Bank Transfer" },
  "ovo":           { Icon: IconEWallet,      label: "OVO" },
  "gopay":         { Icon: IconEWallet,      label: "GoPay" },
  "shopeepay":     { Icon: IconEWallet,      label: "ShopeePay" },
  "qris":          { Icon: IconQRIS,         label: "QRIS" },
};

export const PayIcon = ({ method, size = 13, color }) => {
  const M = PAY_META[method];
  return M ? <M.Icon size={size} color={color} /> : <IconWallet size={size} color={color} />;
};
