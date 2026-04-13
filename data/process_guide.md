# Manufacturing Process Selection Guide
# 製程選擇參考手冊
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

## B — Administrative / Management  (管理製程)

[B01] 繪圖者  (★★ HIGH)
  Trigger  : 基本
  Evidence : See trigger description

[B02] 排版  (★★ HIGH)
  Trigger  : 基本
  Evidence : See trigger description

---

## C — Cutting  (切割)

[C01] 單機切割  (★★ HIGH)
  Trigger  : 基本，有M3048不做
  Evidence : See trigger description

[C04] M2048  (★  MED)
  Trigger  : 由排版去決定分攤M3048的工作
  Evidence : See trigger description

[C05] M3048  (★★ HIGH)
  Trigger  : 圖面，備註規格: 抽牙M3/M4/M5 或製圖拆圖完有註明"中心沖)
  Evidence : TEXT — look for text annotations on drawing

---

## D — Bending & Insert  (折彎 / 植零件)

[D01] 折彎  (★★ HIGH)
  Trigger  : 基本,圖面有折彎的
  Evidence : VISUAL — look for geometric shapes/profiles

[D04] 折彎/植零件  (★★ HIGH)
  Trigger  : 基本;圖面有植零件和折彎同時存在時
  Evidence : VISUAL + TEXT — geometric features AND text annotation

[D06] 植零件  (★★ HIGH)
  Trigger  : 圖面有植零件:壓鉚螺帽;接地螺絲;浮動螺絲…等中文
  Evidence : TEXT — look for text annotations on drawing

[D07] 植零件/折彎  (★  MED)
  Trigger  : 現場或生技回饋要先植再折
  Evidence : See trigger description

---

## E — Surface Finishing  (後處理)

[E01] 去毛邊  (★★ HIGH)
  Trigger  : 基本,去除毛邊+打亂花+攻牙+皿頭
  Evidence : See trigger description

[E02] 去毛邊2  (★  MED)
  Trigger  : 1.有幾家客戶有指定2.0T的厚度若有折,需在折彎後加上「去毛邊2」磨除擠肉  2.折彎後孔變形
  Evidence : See trigger description

---

## F — Welding  (焊接)

[F01] F01 焊接  (★★ HIGH)
  Trigger  : 高;基本,焊接符號或圖面有"焊接"字眼
  Evidence : SYMBOL + TEXT — symbols AND text annotation

[F03] F03 SPOT  (★  MED)
  Trigger  : 圖面有spot 符號 及spot零件(焊接螺帽.點焊螺帽.點焊螺柱 ..)
  Evidence : SYMBOL + TEXT — symbols AND text annotation

[F05] F05 廠內捲圓  (★  MED)
  Trigger  : 圖面上的圓管樣但不在巿購件規格內,直徑大於70mm
  Evidence : VISUAL + TEXT — geometric features AND text annotation

[F06] F06 廠內裁管  (★  MED)
  Trigger  : 一般是指圓棒或零件要裁長度
  Evidence : See trigger description

[F10] F10 植焊螺絲  (★  MED)
  Trigger  : 零件:植焊螺絲(業務依圖決定零件)
  Evidence : See trigger description

[F11] F11 廠內烤漆  (★★ HIGH)
  Trigger  : 1.圖面上有烤漆 2.業務有買色粉或廠內有色粉 3.圖面上有烤漆色號
  Evidence : TEXT (primary) + external info (customer/BOM note)

[F14] F14 焊接研磨  (★★ HIGH)
  Trigger  : 基本，通常接在「焊接」之後
  Evidence : See trigger description

[F16] F16 自動焊接  (★  MED)
  Trigger  : 中;現場回饋,要在自動焊接使用機械手臂焊接
  Evidence : See trigger description

[F20] F20 自動研磨  (★  MED)
  Trigger  : 中;搭配「自動焊接」後的製程
  Evidence : See trigger description

[F25] F25 光纖焊接  (★  MED)
  Trigger  : 現場回饋,可以用「光纖焊接」
  Evidence : See trigger description

---

## H — Cleaning & Packaging  (清洗 / 包裝)

[H01] H01 除焦洗淨  (★★ HIGH)
  Trigger  : 白鐵焊接會需除焦,表處:烤漆則不用除焦
  Evidence : See trigger description

[H02] H02 部品包裝  (★★ HIGH)
  Trigger  : 基本 ;一般都要經過包裝才可出貨
  Evidence : See trigger description

[H03] H03 包裝網蓋貼  (★★ HIGH)
  Trigger  : 圖面上有"網印,蓋印,貼紙"
  Evidence : TEXT — look for text annotations on drawing

[H08] H08 委外前處理  (★★ HIGH)
  Trigger  : 一般要送委外前要包裝好避免碰撞
  Evidence : See trigger description

[H14] H14 廠內鈍化  (★  MED)
  Trigger  : 客戶圖面上有鈍化
  Evidence : TEXT — look for text annotations on drawing

[H26] H26 燕巢無塵室清潔  (★  MED)
  Trigger  : 圖面上有要求在無塵室等級
  Evidence : TEXT — look for text annotations on drawing

[H27] H27 燕巢無塵室包裝  (★  MED)
  Trigger  : 圖面上有要求在無塵室等級
  Evidence : TEXT — look for text annotations on drawing

[H31] H31 燕巢無塵室清潔/包裝  (★  MED)
  Trigger  : 圖面上有要求在無塵室清潔+包裝
  Evidence : TEXT — look for text annotations on drawing

[H32] H32 整理清潔  (★  MED)
  Trigger  : 「化學清洗」之前製程 (ASML專用)
  Evidence : See trigger description

---

## I — Inspection  (品檢)

[I01] 成品全檢  (★★ HIGH)
  Trigger  : 基本,一般指包裝前的品檢
  Evidence : See trigger description

[I02] 成品全檢2  (★★ HIGH)
  Trigger  : 第二次的品檢,工件有焊接或烤漆後的品檢
  Evidence : See trigger description

[I04] 測漏全檢  (★  MED)
  Trigger  : 圖面有測漏或不可漏水
  Evidence : TEXT — look for text annotations on drawing

[I14] 進料檢驗  (★  MED)
  Trigger  : 指巿購件的加工,第一關
  Evidence : See trigger description

[I19] 燕巢無塵室成品全檢  (★  MED)
  Trigger  : 圖面上有要求在無塵室品檢
  Evidence : TEXT — look for text annotations on drawing

---

## K — CNC Machining  (切削)

[K01] 燕巢切削  (★  MED)
  Trigger  : 無法用雷射加工+折彎成型,或公差太小
  Evidence : VISUAL + TEXT — geometric features AND text annotation

---

## O — Special / Design  (特殊 / 設計)

[O02] 設計雷射雕刻  (★★ HIGH)
  Trigger  : 圖上有雕刻
  Evidence : TEXT — look for text annotations on drawing

[O14] 生技課  (★  MED)
  Trigger  : 研發件或測試件完成後的最後一關
  Evidence : See trigger description

---

## Q — Assembly & Treatment  (組裝 / 表處)

[Q01] Q01 組裝  (★★ HIGH)
  Trigger  : 拉打,拉帽,組裝零件或工件組裝
  Evidence : See trigger description

[Q04] Q04 清潔/脫脂/鉻酸鹽  (★  MED)
  Trigger  : 圖面有鉻酸鹽
  Evidence : TEXT — look for text annotations on drawing

[Q07] Q07 防烤/表處遮蔽  (★  MED)
  Trigger  : 圖面上有不烤漆或防烤或請遮蔽字樣
  Evidence : TEXT — look for text annotations on drawing

[Q11] Q11 燕巢無塵室組裝  (★  MED)
  Trigger  : 圖面上有要求在無塵室組裝
  Evidence : TEXT — look for text annotations on drawing

---

## J — Warehouse  (倉庫)

[J01] 燕巢倉庫  (★★ HIGH)
  Trigger  : 基本
  Evidence : See trigger description

---
