# verification_evidence for task 20260916_082420_bd6dceaa

## 1. GSI geocoding API works
$ curl -sL "https://msearch.gsi.go.jp/address-search/AddressSearch?q=%E6%9D%B1%E4%BA%AC%E9%83%BD%E6%B8%8B%E5%B2%A1%E5%B8%82%EF%BC%92%EF%BC%93%EF%BC%91"
→ [{"geometry":{"coordinates":[139.697723,35.66367],"type":"Point"},"type":"Feature","properties":{"addressCode":"","title":"東京都渋谷区"}},{"geometry":{"coordinates":[139.697723,35.66367],"type":"Point"},"type":"Feature","properties":{"addressCode":"","title":"東京都渋谷区"}}]

## 2. disaportal hazard tile data exists per nankai-trough-mcp sources.ts
$ curl -sL "https://raw.githubusercontent.com/mrslbt/nankai-trough-mcp/main/src/data/sources.ts" -A "Mozilla/5.0" 2>/dev/null | grep -i disaportal
    url: "https://disaportal.gsi.go.jp/",
    url: "https://www.j-shis.bosai.go.jp/",

## 3. nankai-trough-mcp sources.ts shows official JP gov data ingestion
$ curl -sL "https://raw.githubusercontent.com/mrslbt/nankai-trough-mcp/main/src/data/sources.ts" -A "Mozilla/5.0" 2>/dev/null | grep -A 2 -B 2 "gsi\|mlit\|内閣府\|地震本部\|気象庁"
  gsi: {
    name_en: "Geospatial Information Authority of Japan (GSI)",
    name_ja: "国土地理院",
    url: "https://www.gsi.go.jp/",
  },
  disaportal: {
    name_en: "MLIT/GSI National Hazard Map Portal (Kasaneru Hazard Map)",
    name_ja: "国土交通省 ハザードマップポータルサイト（重ねるハザードマップ）\n",
    mlitTaishin: {
    name_en: "MLIT Home Seismic Retrofitting (Sumai no Taishin-ka)",
    name_ja: "国土交通省 住まいの耐震化",
    url: "https://www.mlit.go.jp/jutakukentiku/house/jutakukentiku_house_fr_000043.html",
  },
