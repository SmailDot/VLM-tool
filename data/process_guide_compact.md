PROCESS SELECTION GUIDE — select ALL processes that match evidence in this drawing.
Format your Section 4 as: - [ID] Name: <what you saw>

[B01] 繪圖者 ★ALWAYS → always required (administrative step)
[B02] 排版 ★ALWAYS → always required (administrative step)
[C01] 單機切割 ★ALWAYS → always required for primary laser profile cutting; not required if M3048 (NCT forming) is assigned
[C04] M2048 → layout/nesting engineer decides whether to split the workload with M3048
[C05] M3048 [TEXT] → drawing notes specify: extruded hole tapping M3/M4/M5, or "center punch" annotation present
[D01] 折彎 [VISUAL] → always required when bending features (flanges, profiles) are present in the drawing
[D04] 折彎/植零件 [VISUAL+TEXT] → always required when both hardware insertion and bending features coexist in the drawing
[D06] 植零件 [TEXT] → drawing specifies hardware: press-nut, grounding screw, floating nut, standoff, etc.
[D07] 植零件/折彎 → shop floor or ME feedback: hardware must be inserted before bending sequence
[E01] 去毛邊 ★ALWAYS → always required: deburring + orbital sanding + tapping + countersink finishing
[E02] 去毛邊2 → 1. certain customers require secondary deburring for ≥2.0mm thickness to remove material squeeze after bending; 2. apply if holes deform post-bending
[F01] F01 焊接 [SYMBOL+TEXT] → high-priority; always required when weld symbols or "WELD" annotations appear on the drawing
[F03] F03 SPOT [SYMBOL+TEXT] → drawing shows spot weld symbols or spot-weld hardware (weld nuts, weld studs, etc.)
[F05] F05 廠內捲圓 [VISUAL+TEXT] → drawing shows a cylindrical profile NOT available as a standard commercial part, diameter > 70mm
[F06] F06 廠內裁管 → applies when round bars or structural tube stock require custom length cutting
[F10] F10 植焊螺絲 → part list: weld studs required (sales determines specific hardware based on drawing)
[F11] F11 廠內烤漆 [TEXT+EXT] → 1. drawing specifies powder coating; 2. powder is available from sales; 3. paint color code annotated on drawing
[F14] F14 焊接研磨 → always required; follows welding as a mandatory post-weld grinding step
[F16] F16 自動焊接 → medium-priority; shop floor requests robotic arm for automated welding
[F20] F20 自動研磨 → medium-priority; paired as mandatory post-process after automated welding
[F25] F25 光纖焊接 → shop floor feedback: fiber laser welding applicable for this part
[H01] H01 除焦洗淨 → required after stainless steel welding; NOT required if surface treatment is powder coating
[H02] H02 部品包裝 ★ALWAYS → always required; all parts must undergo final packaging before shipment
[H03] H03 包裝網蓋貼 [TEXT] → drawing specifies screen printing, stamping, or label application
[H08] H08 委外前處理 ★ALWAYS → always required before outsourcing; parts must be packaged to prevent transit damage
[H14] H14 廠內鈍化 [TEXT] → customer drawing specifies passivation treatment
[H26] H26 燕巢無塵室清潔 [TEXT] → drawing specifies cleanroom-grade cleaning requirement
[H27] H27 燕巢無塵室包裝 [TEXT] → drawing specifies cleanroom-grade packaging requirement
[H31] H31 燕巢無塵室清潔/包裝 [TEXT] → drawing specifies both cleanroom cleaning AND cleanroom packaging
[H32] H32 整理清潔 → preparatory step before chemical cleaning (specifically for ASML projects)
[I01] 成品全檢 ★ALWAYS → always required; standard quality inspection before packaging
[I02] 成品全檢2 → secondary inspection pass; required after welding or powder coating operations
[I04] 測漏全檢 [TEXT] → drawing specifies leak testing or waterproofing requirements
[I14] 進料檢驗 → first-gate incoming inspection for purchased commercial parts
[I19] 燕巢無塵室成品全檢 [TEXT] → drawing requires final inspection to be performed within a cleanroom
[O02] 設計雷射雕刻 [TEXT] → drawing specifies laser engraving or marking
[O14] 生技課 → final quality gate for R&D prototypes or test samples before delivery
[Q01] Q01 組裝 → assembly operations: pull-riveting, pull-nuts, hardware integration, or sub-assembly joining
[Q04] Q04 清潔/脫脂/鉻酸鹽 [TEXT] → drawing specifies chromate conversion coating (Alodine)
[Q07] Q07 防烤/表處遮蔽 [TEXT] → drawing notes: "No Paint", "Anti-paint", or "Masking Required"
[Q11] Q11 燕巢無塵室組裝 [TEXT] → drawing requires assembly to be performed within a cleanroom environment
[K01] 燕巢切削 [VISUAL+TEXT] → features cannot be achieved by laser and bending alone, or tolerances are too tight for standard sheet metal
[J01] 燕巢倉庫 ★ALWAYS → always required (warehouse/inventory step)
