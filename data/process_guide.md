# Manufacturing Process Selection Guide
# Source: NKUST AIIAStudents Lab — 2026-01 (High + Medium frequency only)

## HOW TO USE THIS GUIDE
You are a QA inspector analyzing a 2D engineering drawing.
For each process entry below:
  1. Read the TRIGGER (when to select this process)
  2. Look at the drawing for the EVIDENCE TYPE listed
  3. If you find matching evidence → select this process in Section 4
  4. Be conservative: only select if you have CLEAR visual or textual evidence in the drawing
  5. Administrative processes (B01, B02, J01) are ALWAYS selected unless otherwise noted

---

## B — Administrative / Management

[B01] 繪圖者  (★★ HIGH)
  Trigger  : always required (administrative step)
  Evidence : See trigger description

[B02] 排版  (★★ HIGH)
  Trigger  : always required (administrative step)
  Evidence : See trigger description

---

## C — Cutting

[C01] 單機切割  (★★ HIGH)
  Trigger  : always required for primary laser profile cutting; not required if M3048 (NCT forming) is assigned
  Evidence : See trigger description

[C04] M2048  (★  MED)
  Trigger  : layout/nesting engineer decides whether to split the workload with M3048
  Evidence : See trigger description

[C05] M3048  (★★ HIGH)
  Trigger  : drawing notes specify extruded hole tapping M3/M4/M5, or "center punch" annotation present
  Evidence : TEXT — look for text annotations on drawing

---

## D — Bending & Insert

[D01] 折彎  (★★ HIGH)
  Trigger  : always required when bending features (flanges, profiles) are present in the drawing
  Evidence : VISUAL — look for geometric shapes/profiles

[D04] 折彎/植零件  (★★ HIGH)
  Trigger  : always required when both hardware insertion and bending features coexist in the drawing
  Evidence : VISUAL + TEXT — geometric features AND text annotation

[D06] 植零件  (★★ HIGH)
  Trigger  : drawing specifies hardware: press-nut, grounding screw, floating nut, standoff, etc.
  Evidence : TEXT — look for text annotations on drawing

[D07] 植零件/折彎  (★  MED)
  Trigger  : shop floor or ME feedback: hardware must be inserted before bending sequence
  Evidence : See trigger description

---

## E — Surface Finishing

[E01] 去毛邊  (★★ HIGH)
  Trigger  : always required: deburring + orbital sanding + tapping + countersink finishing
  Evidence : See trigger description

[E02] 去毛邊2  (★  MED)
  Trigger  : 1. certain customers require secondary deburring for ≥2.0mm thickness to remove material squeeze after bending; 2. apply if holes deform post-bending
  Evidence : See trigger description

---

## F — Welding

[F01] F01 焊接  (★★ HIGH)
  Trigger  : high-priority; always required when weld symbols or "WELD" annotations appear on the drawing
  Evidence : SYMBOL + TEXT — symbols AND text annotation

[F03] F03 SPOT  (★  MED)
  Trigger  : drawing shows spot weld symbols or spot-weld hardware (weld nuts, weld studs, etc.)
  Evidence : SYMBOL + TEXT — symbols AND text annotation

[F05] F05 廠內捲圓  (★  MED)
  Trigger  : drawing shows a cylindrical profile NOT available as a standard commercial part, diameter > 70mm
  Evidence : VISUAL + TEXT — geometric features AND text annotation

[F06] F06 廠內裁管  (★  MED)
  Trigger  : applies when round bars or structural tube stock require custom length cutting
  Evidence : See trigger description

[F10] F10 植焊螺絲  (★  MED)
  Trigger  : part list: weld studs required (sales determines specific hardware based on drawing)
  Evidence : See trigger description

[F11] F11 廠內烤漆  (★★ HIGH)
  Trigger  : 1. drawing specifies powder coating; 2. powder is available from sales; 3. paint color code annotated on drawing
  Evidence : TEXT (primary) + external info (customer/BOM note)

[F14] F14 焊接研磨  (★★ HIGH)
  Trigger  : always required; follows welding as a mandatory post-weld grinding step
  Evidence : See trigger description

[F16] F16 自動焊接  (★  MED)
  Trigger  : medium-priority; shop floor requests robotic arm for automated welding
  Evidence : See trigger description

[F20] F20 自動研磨  (★  MED)
  Trigger  : medium-priority; paired as mandatory post-process after automated welding
  Evidence : See trigger description

[F25] F25 光纖焊接  (★  MED)
  Trigger  : shop floor feedback: fiber laser welding applicable for this part
  Evidence : See trigger description

---

## H — Cleaning & Packaging

[H01] H01 除焦洗淨  (★★ HIGH)
  Trigger  : required after stainless steel welding; NOT required if surface treatment is powder coating
  Evidence : See trigger description

[H02] H02 部品包裝  (★★ HIGH)
  Trigger  : always required; all parts must undergo final packaging before shipment
  Evidence : See trigger description

[H03] H03 包裝網蓋貼  (★★ HIGH)
  Trigger  : drawing specifies screen printing, stamping, or label application
  Evidence : TEXT — look for text annotations on drawing

[H08] H08 委外前處理  (★★ HIGH)
  Trigger  : always required before outsourcing; parts must be packaged to prevent transit damage
  Evidence : See trigger description

[H14] H14 廠內鈍化  (★  MED)
  Trigger  : customer drawing specifies passivation treatment
  Evidence : TEXT — look for text annotations on drawing

[H26] H26 燕巢無塵室清潔  (★  MED)
  Trigger  : drawing specifies cleanroom-grade cleaning requirement
  Evidence : TEXT — look for text annotations on drawing

[H27] H27 燕巢無塵室包裝  (★  MED)
  Trigger  : drawing specifies cleanroom-grade packaging requirement
  Evidence : TEXT — look for text annotations on drawing

[H31] H31 燕巢無塵室清潔/包裝  (★  MED)
  Trigger  : drawing specifies both cleanroom cleaning AND cleanroom packaging
  Evidence : TEXT — look for text annotations on drawing

[H32] H32 整理清潔  (★  MED)
  Trigger  : preparatory step before chemical cleaning (specifically for ASML projects)
  Evidence : See trigger description

---

## I — Inspection

[I01] 成品全檢  (★★ HIGH)
  Trigger  : always required; standard quality inspection performed before packaging
  Evidence : See trigger description

[I02] 成品全檢2  (★★ HIGH)
  Trigger  : secondary inspection pass; required after welding or powder coating operations
  Evidence : See trigger description

[I04] 測漏全檢  (★  MED)
  Trigger  : drawing specifies leak testing or waterproofing requirements
  Evidence : TEXT — look for text annotations on drawing

[I14] 進料檢驗  (★  MED)
  Trigger  : first-gate incoming inspection for purchased commercial parts
  Evidence : See trigger description

[I19] 燕巢無塵室成品全檢  (★  MED)
  Trigger  : drawing requires final inspection to be performed within a cleanroom
  Evidence : TEXT — look for text annotations on drawing

---

## K — CNC Machining

[K01] 燕巢切削  (★  MED)
  Trigger  : features cannot be achieved by laser and bending alone, or tolerances are too tight for standard sheet metal
  Evidence : VISUAL + TEXT — geometric features AND text annotation

---

## O — Special / Design

[O02] 設計雷射雕刻  (★★ HIGH)
  Trigger  : drawing specifies laser engraving or marking
  Evidence : TEXT — look for text annotations on drawing

[O14] 生技課  (★  MED)
  Trigger  : final quality gate for R&D prototypes or test samples before delivery
  Evidence : See trigger description

---

## Q — Assembly & Treatment

[Q01] Q01 組裝  (★★ HIGH)
  Trigger  : assembly operations: pull-riveting, pull-nuts, hardware integration, or sub-assembly joining
  Evidence : See trigger description

[Q04] Q04 清潔/脫脂/鉻酸鹽  (★  MED)
  Trigger  : drawing specifies chromate conversion coating (Alodine)
  Evidence : TEXT — look for text annotations on drawing

[Q07] Q07 防烤/表處遮蔽  (★  MED)
  Trigger  : drawing notes: "No Paint", "Anti-paint", or "Masking Required"
  Evidence : TEXT — look for text annotations on drawing

[Q11] Q11 燕巢無塵室組裝  (★  MED)
  Trigger  : drawing requires assembly to be performed within a cleanroom environment
  Evidence : TEXT — look for text annotations on drawing

---

## J — Warehouse

[J01] 燕巢倉庫  (★★ HIGH)
  Trigger  : always required (warehouse/inventory step)
  Evidence : See trigger description

---
