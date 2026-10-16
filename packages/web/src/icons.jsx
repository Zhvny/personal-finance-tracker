// ─── icons.jsx ────────────────────────────────────────────────────────────────
// Central icon registry — Single Source of Truth for all icons in the app.
//
// Clean Architecture : UI components never import icon libraries directly.
//                      They import from here. Swapping libraries = 1 file change.
// DRY               : icon size/color defaults defined once.
// Abstraction       : consumers use semantic names (IconAdd, IconSell…),
//                     not library-specific component names.
//
// Libraries used:
//   react-icons  → https://react-icons.github.io/react-icons  (primary)
//   phosphor-react (fallback set, richer style variety)
//   @mui/icons-material (MUI set, material design icons)
//
// Run: npm install   (package.json already has all three as dependencies)
// ─────────────────────────────────────────────────────────────────────────────

// ── react-icons imports (primary) ─────────────────────────────────────────────
// Using multiple sub-sets to pick the most expressive icon per context.
import {
  // Navigation / Layout
  RiDashboardLine,
  RiPieChartLine,
  RiBarChartLine,
  RiLineChartLine,
  RiMenuFoldLine,
  RiMenuUnfoldLine,
  // Finance
  RiMoneyDollarCircleLine,
  RiBankLine,
  RiCoinLine,
  RiBitCoinLine,
  RiStockLine,
  // Actions
  RiAddLine,
  RiDeleteBinLine,
  RiEditLine,
  RiRefreshLine,
  RiSearchLine,
  RiFilterLine,
  RiDownloadLine,
  RiUploadLine,
  RiCheckLine,
  RiCloseLine,
  RiFlashlightLine,
  // Status / Indicators
  RiArrowUpLine,
  RiArrowDownLine,
  RiAlertLine,
  RiInformationLine,
  RiCheckboxCircleLine,
  RiErrorWarningLine,
  RiFireLine,
  // Categories
  RiRestaurantLine,
  RiCarLine,
  RiHome2Line,
  RiGamepadLine,
  RiHeartPulseLine,
  RiShoppingBag2Line,
  RiBookOpenLine,
  RiBarChart2Line,
  RiArchiveLine,
  // Misc
  RiCalendarLine,
  RiTimeLine,
  RiFileTextLine,
  RiScanLine,
  RiLockLine,
  RiMindMap,
  RiShieldCheckLine,
  RiWalletLine,
  RiPercentLine,
  // Gank-patreon specific
  RiTrophyLine,
  RiMedalLine,
  RiStarLine,
  RiImageLine,
  RiVideoLine,
  RiLeafLine,
  RiFlashlightFill,
  RiShoppingCart2Line,
  RiMoonLine,
  RiSunLine,
  RiStoreLine,
  RiGiftLine,
  RiCopperCoinLine,
  RiLockUnlockLine,
  RiSettings3Line,
  RiUserLine,
  RiBriefcaseLine,
} from "react-icons/ri";

import { GiCrossedSwords } from "react-icons/gi";

import {
  BsCurrencyDollar,
  BsGraphUpArrow,
  BsGraphDownArrow,
  BsLightningChargeFill,
  BsCash,
  BsCreditCard2Front,
  BsQrCode,
  BsPhone,
  BsBank,
  BsGem,
} from "react-icons/bs";

import {
  TbPigMoney,
  TbCurrencyBitcoin,
  TbBrain,
  TbChartTreemap,
  TbReportMoney,
  TbReceipt,
  TbTrendingUp,
  TbTrendingDown,
  TbBuildingBank,
  TbChartInfographic,
  // Gank-patreon
  TbTarget,
  TbAward,
  TbRotate,
  TbCoin,
  TbFlame,
  TbBolt,
  TbSparkles,
  TbCalendarStats,
  TbRepeat,
  TbShieldStar,
  TbPlayerPlay,
  TbPhoto,
  TbCamera,
  TbList,
  TbCategory,
  TbCalculator,
  TbChartDonut,
  TbLayoutList,
  TbBriefcase,
  TbDeviceLaptop,
  TbShoppingCart,
  TbCards,
  TbLayoutDashboard,
  TbArrowsUpDown,
  TbTrash,
  TbPencil,
  TbX,
  TbPlus,
  TbCheck,
  TbRefresh,
  TbSearch,
  TbWallet,
  TbCurrencyDollar as TbCurrencyDollarIcon,
  TbChartBar,
  TbChevronRight,
  TbDots,
} from "react-icons/tb";

// ── Default props factory ─────────────────────────────────────────────────────
const sz = (size = 16) => ({ size, style: { flexShrink: 0, display: "block" } });

// ── Named icon exports (semantic names) ───────────────────────────────────────

// — Navigation
export const IconDashboard    = (p) => <RiDashboardLine     {...sz(p.size)} {...p} />;
export const IconUser         = (p) => <RiUserLine          {...sz(p.size)} {...p} />;
export const IconBusiness     = (p) => <RiBriefcaseLine     {...sz(p.size)} {...p} />;
export const IconInvestment   = (p) => <RiStockLine         {...sz(p.size)} {...p} />;
export const IconExpense      = (p) => <RiMoneyDollarCircleLine {...sz(p.size)} {...p} />;
export const IconIncome       = (p) => <TbPigMoney          {...sz(p.size)} {...p} />;
export const IconReceipt      = (p) => <TbReceipt           {...sz(p.size)} {...p} />;
export const IconBehavioral   = (p) => <TbBrain             {...sz(p.size)} {...p} />;
export const IconMenuClose    = (p) => <RiMenuFoldLine       {...sz(p.size)} {...p} />;
export const IconMenuOpen     = (p) => <RiMenuUnfoldLine     {...sz(p.size)} {...p} />;

// — Finance / Asset types
export const IconStock        = (p) => <BsGraphUpArrow      {...sz(p.size)} {...p} />;
export const IconCrypto       = (p) => <TbCurrencyBitcoin   {...sz(p.size)} {...p} />;
export const IconGold         = (p) => <BsGem               {...sz(p.size)} {...p} />;
export const IconCash         = (p) => <BsCash              {...sz(p.size)} {...p} />;
export const IconBank         = (p) => <TbBuildingBank      {...sz(p.size)} {...p} />;
export const IconWallet       = (p) => <RiWalletLine        {...sz(p.size)} {...p} />;
export const IconDebt         = (p) => <BsCreditCard2Front  {...sz(p.size)} {...p} />;
export const IconShieldCheck  = (p) => <RiShieldCheckLine   {...sz(p.size)} {...p} />;
export const IconActivity     = (p) => <RiHeartPulseLine    {...sz(p.size)} {...p} />;

// — Payment methods
export const IconCashPay      = (p) => <BsCash              {...sz(p.size)} {...p} />;
export const IconDebitCard    = (p) => <BsCreditCard2Front  {...sz(p.size)} {...p} />;
export const IconCreditCard   = (p) => <BsCreditCard2Front  {...sz(p.size)} {...p} />;
export const IconEWallet      = (p) => <BsPhone             {...sz(p.size)} {...p} />;
export const IconBankTransfer = (p) => <BsBank              {...sz(p.size)} {...p} />;
export const IconQRIS         = (p) => <BsQrCode            {...sz(p.size)} {...p} />;

// — Actions
export const IconAdd          = (p) => <RiAddLine           {...sz(p.size)} {...p} />;
export const IconDelete       = (p) => <RiDeleteBinLine     {...sz(p.size)} {...p} />;
export const IconEdit         = (p) => <RiEditLine          {...sz(p.size)} {...p} />;
export const IconRefresh      = (p) => <RiRefreshLine       {...sz(p.size)} {...p} />;
export const IconSearch       = (p) => <RiSearchLine        {...sz(p.size)} {...p} />;
export const IconFilter       = (p) => <RiFilterLine        {...sz(p.size)} {...p} />;
export const IconDownload     = (p) => <RiDownloadLine      {...sz(p.size)} {...p} />;
export const IconUpload       = (p) => <RiUploadLine        {...sz(p.size)} {...p} />;
export const IconCheck        = (p) => <RiCheckLine         {...sz(p.size)} {...p} />;
export const IconClose        = (p) => <RiCloseLine         {...sz(p.size)} {...p} />;
export const IconX            = IconClose;
export const IconSell         = (p) => <RiFireLine          {...sz(p.size)} {...p} />;
export const IconScan         = (p) => <RiScanLine          {...sz(p.size)} {...p} />;
export const IconClean        = (p) => <RiDeleteBinLine     {...sz(p.size)} {...p} />;

// — Trend / Status
export const IconUp           = (p) => <TbTrendingUp        {...sz(p.size)} {...p} />;
export const IconDown         = (p) => <TbTrendingDown      {...sz(p.size)} {...p} />;
export const IconAlert        = (p) => <RiAlertLine         {...sz(p.size)} {...p} />;
export const IconInfo         = (p) => <RiInformationLine   {...sz(p.size)} {...p} />;
export const IconSuccess      = (p) => <RiCheckboxCircleLine {...sz(p.size)} {...p} />;
export const IconWarning      = (p) => <RiErrorWarningLine  {...sz(p.size)} {...p} />;
export const IconAlertCircle  = (p) => <RiErrorWarningLine  {...sz(p.size)} {...p} />;

// — Analysis / Charts
export const IconPieChart     = (p) => <RiPieChartLine      {...sz(p.size)} {...p} />;
export const IconBarChart     = (p) => <RiBarChartLine      {...sz(p.size)} {...p} />;
export const IconLineChart    = (p) => <RiLineChartLine     {...sz(p.size)} {...p} />;
export const IconHeatmap      = (p) => <TbChartTreemap      {...sz(p.size)} {...p} />;
export const IconRisk         = (p) => <TbChartInfographic  {...sz(p.size)} {...p} />;
export const IconFBS          = (p) => <TbReportMoney       {...sz(p.size)} {...p} />;
export const IconShield       = (p) => <RiShieldCheckLine   {...sz(p.size)} {...p} />;
export const IconPercent      = (p) => <RiPercentLine       {...sz(p.size)} {...p} />;

// — Expense Categories
export const IconFood         = (p) => <RiRestaurantLine    {...sz(p.size)} {...p} />;
export const IconTransport    = (p) => <RiCarLine           {...sz(p.size)} {...p} />;
export const IconHousing      = (p) => <RiHome2Line         {...sz(p.size)} {...p} />;
export const IconEntertainment= (p) => <RiGamepadLine       {...sz(p.size)} {...p} />;
export const IconHealth       = (p) => <RiHeartPulseLine    {...sz(p.size)} {...p} />;
export const IconShopping     = (p) => <RiShoppingBag2Line  {...sz(p.size)} {...p} />;
export const IconEducation    = (p) => <RiBookOpenLine       {...sz(p.size)} {...p} />;
export const IconOther        = (p) => <RiArchiveLine       {...sz(p.size)} {...p} />;

// — Misc
export const IconCalendar     = (p) => <RiCalendarLine      {...sz(p.size)} {...p} />;
export const IconTime         = (p) => <RiTimeLine          {...sz(p.size)} {...p} />;
export const IconFile         = (p) => <RiFileTextLine      {...sz(p.size)} {...p} />;
export const IconFlash        = (p) => <BsLightningChargeFill {...sz(p.size)} {...p} />;

// ── Category → icon map (mirrors CAT_ICON in constants.js, DRY for JSX) ──────
export const CAT_ICON_JSX = {
  "Food & Drink": (p) => <IconFood          {...p} />,
  transport:     (p) => <IconTransport     {...p} />,
  housing:       (p) => <IconHousing       {...p} />,
  entertainment: (p) => <IconEntertainment {...p} />,
  health:        (p) => <IconHealth        {...p} />,
  shopping:      (p) => <IconShopping      {...p} />,
  education:     (p) => <IconEducation     {...p} />,
  investment:    (p) => <IconInvestment    {...p} />,
  other:         (p) => <IconOther         {...p} />,
};

// ── Asset type → icon map ─────────────────────────────────────────────────────
export const ASSET_ICON_JSX = {
  stock:  (p) => <IconStock  {...p} />,
  crypto: (p) => <IconCrypto {...p} />,
  gold:   (p) => <IconGold   {...p} />,
};

// ── Payment method → icon map ─────────────────────────────────────────────────
export const PAY_ICON_JSX = {
  "cash":          (p) => <IconCashPay      {...p} />,
  "debit-card":    (p) => <IconDebitCard    {...p} />,
  "credit-card":   (p) => <IconCreditCard   {...p} />,
  "e-wallet":      (p) => <IconEWallet      {...p} />,
  "bank-transfer": (p) => <IconBankTransfer {...p} />,
  "ovo":           (p) => <IconEWallet      {...p} />,
  "gopay":         (p) => <IconEWallet      {...p} />,
  "shopeepay":     (p) => <IconEWallet      {...p} />,
  "qris":          (p) => <IconQRIS         {...p} />,
};

// — Navigation page → icon map ────────────────────────────────────────────────
export const NAV_ICON_JSX = {
  dashboard:   (p) => <IconDashboard   {...p} />,
  investments: (p) => <IconInvestment  {...p} />,
  expenses:    (p) => <IconExpense     {...p} />,
  income:      (p) => <IconIncome      {...p} />,
  stocks:      (p) => <IconStocks      {...p} />,
  ml_stocks:   (p) => <IconML          {...p} />,
  genetic:     (p) => <TbChartTreemap  {...sz(p.size)} {...p} />,
  receipt:     (p) => <IconReceipt     {...p} />,
  behavioral:  (p) => <IconBehavioral  {...p} />,
  earn:        (p) => <IconStreak       {...p} />,
  advanced:    (p) => <IconTarget       {...p} />,
  analytics:   (p) => <IconBarChart     {...p} />,
};

// ── Gank-Patreon / Earn-Your-Content icons ────────────────────────────────────
export const IconSave         = (p) => <RiCopperCoinLine    {...sz(p.size)} {...p} />;
export const IconStreak       = (p) => <TbFlame             {...sz(p.size)} {...p} />;
export const IconZap          = (p) => <TbBolt               {...sz(p.size)} {...p} />;
export const IconStar         = (p) => <RiStarLine          {...sz(p.size)} {...p} />;
export const IconTrophy       = (p) => <RiTrophyLine        {...sz(p.size)} {...p} />;
export const IconMedal        = (p) => <RiMedalLine         {...sz(p.size)} {...p} />;
export const IconAward        = (p) => <TbAward             {...sz(p.size)} {...p} />;
export const IconShieldStar   = (p) => <TbShieldStar        {...sz(p.size)} {...p} />;
export const IconTarget       = (p) => <TbTarget            {...sz(p.size)} {...p} />;
export const IconSword        = (p) => <GiCrossedSwords     {...sz(p.size)} {...p} />;
export const IconSparkles     = (p) => <TbSparkles          {...sz(p.size)} {...p} />;
export const IconCoin         = (p) => <TbCoin              {...sz(p.size)} {...p} />;
export const IconLeaf         = (p) => <RiLeafLine          {...sz(p.size)} {...p} />;
export const IconMoon         = (p) => <RiMoonLine          {...sz(p.size)} {...p} />;
export const IconSun          = (p) => <RiSunLine           {...sz(p.size)} {...p} />;
export const IconVexBolt      = (p) => <TbBolt              {...sz(p.size)} {...p} />;
export const IconStore        = (p) => <RiStoreLine         {...sz(p.size)} {...p} />;
export const IconGift         = (p) => <RiGiftLine          {...sz(p.size)} {...p} />;
export const IconUnlock       = (p) => <RiLockUnlockLine    {...sz(p.size)} {...p} />;
export const IconImage        = (p) => <TbPhoto             {...sz(p.size)} {...p} />;
export const IconVideo        = (p) => <TbPlayerPlay        {...sz(p.size)} {...p} />;
export const IconRepeat       = (p) => <TbRepeat            {...sz(p.size)} {...p} />;
export const IconCalStat      = (p) => <TbCalendarStats     {...sz(p.size)} {...p} />;
export const IconNoSpend      = (p) => <RiShoppingCart2Line {...sz(p.size)} {...p} />;
export const IconMultiplier   = (p) => <RiFlashlightFill    {...sz(p.size)} {...p} />;
export const IconPenalty      = (p) => <RiErrorWarningLine  {...sz(p.size)} {...p} />;
export const IconMilestone    = (p) => <TbSparkles          {...sz(p.size)} {...p} />;
export const IconSeason       = (p) => <TbRotate            {...sz(p.size)} {...p} />;
export const IconRank         = (p) => <RiTrophyLine        {...sz(p.size)} {...p} />;

// — Section / Page icons (replaces emojis)
export const IconPortfolio    = (p) => <TbLayoutList        {...sz(p.size)} {...p} />;
export const IconAnalysis     = (p) => <TbChartDonut        {...sz(p.size)} {...p} />;
export const IconPLReport     = (p) => <TbChartBar          {...sz(p.size)} {...p} />;
export const IconTransactions = (p) => <TbCards             {...sz(p.size)} {...p} />;
export const IconBudget       = (p) => <TbCategory          {...sz(p.size)} {...p} />;
export const IconSummary      = (p) => <TbLayoutDashboard   {...sz(p.size)} {...p} />;
export const IconLayoutDashboard = IconSummary;
export const IconRecords      = (p) => <TbList              {...sz(p.size)} {...p} />;
export const IconTax          = (p) => <TbCalculator        {...sz(p.size)} {...p} />;
export const IconCamera       = (p) => <TbCamera            {...sz(p.size)} {...p} />;
export const IconSalary       = (p) => <TbBriefcase         {...sz(p.size)} {...p} />;
export const IconFreelance    = (p) => <TbDeviceLaptop      {...sz(p.size)} {...p} />;
export const IconSideHustle   = (p) => <TbShoppingCart      {...sz(p.size)} {...p} />;
export const IconNetWorth     = (p) => <TbBuildingBank      {...sz(p.size)} {...p} />;
export const IconInsight      = (p) => <TbArrowsUpDown      {...sz(p.size)} {...p} />;
export const IconArrowRight   = (p) => <TbChevronRight      {...sz(p.size)} {...p} />;
export const IconStocks       = (p) => <TbChartTreemap      {...sz(p.size)} {...p} />;
export const IconML           = (p) => <TbBrain             {...sz(p.size)} {...p} />;
export const IconMore         = (p) => <TbDots              {...sz(p.size)} {...p} />;
export const IconSettings     = (p) => <RiSettings3Line     {...sz(p.size)} {...p} />;
