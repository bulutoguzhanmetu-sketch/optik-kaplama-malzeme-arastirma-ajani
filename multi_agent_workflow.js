export const meta = {
  name: 'optik-kaplama-multi-agent-rapor',
  description: 'Optik kaplama PDF kanit tabanindan cok ajanli, atif-dogrulamali rapor uretir',
  phases: [
    { title: 'Kaynak Toplama', detail: 'ChromaDB kanit tabanindan pasajlari cek' },
    { title: 'Cok Acili Sentez', detail: 'Farkli uzmanlik acilarindan bulgu cikarimi' },
    { title: 'Dogrulama', detail: 'Her iddiayi kaynagina karsi adversarial dogrula' },
    { title: 'Sentezleme', detail: 'Dogrulanmis bulgulardan nihai rapor metni uret' },
  ],
}

const REPO_DIR = '<REPO_DIR_BURAYA>'

const PASSAGES_SCHEMA = {
  type: 'object',
  properties: {
    passages: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          index: { type: 'number' },
          source: { type: 'string' },
          page: { type: 'string' },
          text: { type: 'string' },
        },
        required: ['index', 'source', 'page', 'text'],
      },
    },
  },
  required: ['passages'],
}

const CLAIMS_SCHEMA = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          passage_index: { type: 'number' },
        },
        required: ['claim', 'passage_index'],
      },
    },
  },
  required: ['lens', 'claims'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    supported: { type: 'boolean' },
    reasoning: { type: 'string' },
  },
  required: ['supported', 'reasoning'],
}

const FINAL_SCHEMA = {
  type: 'object',
  properties: {
    giris: { type: 'string' },
    bulgular: { type: 'string' },
    sonuc: { type: 'string' },
    kaynakca: { type: 'array', items: { type: 'string' } },
  },
  required: ['giris', 'bulgular', 'sonuc', 'kaynakca'],
}

const LENSES = [
  { key: 'malzeme', prompt: 'malzeme ozellikleri (kristal yapi, optik bant araligi, mekanik/termal dayanim)' },
  { key: 'uretim', prompt: 'uretim ve isleme yontemleri (kaplama teknikleri, sentez, yuzey hazirlama)' },
  { key: 'performans', prompt: 'optik/IR performansi (gecirgenlik, yansima, dalga boyu araligi, dayaniklilik)' },
]

let parsedArgs = args
if (typeof parsedArgs === 'string') {
  try {
    parsedArgs = JSON.parse(parsedArgs)
  } catch (e) {
    parsedArgs = { topic: parsedArgs }
  }
}

const topic = parsedArgs && parsedArgs.topic
if (!topic) {
  throw new Error('args.topic gerekli, gelen args: ' + JSON.stringify(args))
}

phase('Kaynak Toplama')
const retrieval = await agent(
  `Su bash komutunu calistir: cd "${REPO_DIR}" && python3 coating_agent/report_generator.py "${topic}" --sadece-kaynaklar --json
Komutun stdout ciktisi tek satirlik bir JSON nesnesi olacak: {"passages": [{"index":.., "source":.., "page":.., "text":..}, ...]}.
Bu JSON'u oldugu gibi parse et ve ayni yapida structured output dondur. Yorumlama, ekleme/cikarma yapma, oldugu gibi ilet. Eger komut hata verirse veya passages bos ise, bos bir passages listesi dondur.`,
  { schema: PASSAGES_SCHEMA, label: 'retrieve' }
)

const passages = (retrieval && retrieval.passages) || []
log(`${passages.length} pasaj bulundu.`)

if (passages.length === 0) {
  return {
    topic,
    report: { giris: '', bulgular: 'Kanit tabaninda bu konuyla iliskili hic pasaj bulunamadi.', sonuc: '', kaynakca: [] },
    claims_total: 0,
    claims_verified: 0,
    sources: [],
  }
}

const passagesText = passages.map(p => `[${p.index}] (Kaynak: ${p.source}, s. ${p.page})\n${p.text}`).join('\n\n')

phase('Cok Acili Sentez')
const lensResults = await pipeline(
  LENSES,
  lens => agent(
    `Sen bir optik kaplama ve malzeme muhendisisin. Asagidaki kaynak pasajlara dayanarak SADECE "${lens.prompt}" acisindan, pasajlarda fiilen yazili olan bulgulari cikar. Her bulgu icin, hangi pasaj numarasindan (index) geldigini belirt. Pasajlarda bu acidan bilgi yoksa bos claims listesi dondur. Pasajlar disinda hic bilgi ekleme.\n\nPasajlar:\n\n${passagesText}`,
    { schema: CLAIMS_SCHEMA, phase: 'Cok Acili Sentez', label: `sentez:${lens.key}` }
  ),
  (claimsResult, lens) => {
    if (!claimsResult || !claimsResult.claims || claimsResult.claims.length === 0) return []
    return parallel(
      claimsResult.claims.map(c => () => {
        const p = passages.find(x => x.index === c.passage_index)
        const passageText = p ? p.text : '(pasaj bulunamadi)'
        return agent(
          `Su iddiayi, verilen kaynak pasajla karsilastirarak adversarial sekilde degerlendir. Iddia gercekten bu pasajda yazilanlarla destekleniyor mu, yoksa pasajda olmayan bir sey mi ekleniyor/abartiliyor? Emin degilsen supported=false yap.\n\nIddia: "${c.claim}"\n\nKaynak pasaj (s. ${p ? p.page : '?'}, ${p ? p.source : '?'}):\n${passageText}`,
          { schema: VERDICT_SCHEMA, phase: 'Dogrulama', label: `dogrula:${lens.key}` }
        ).then(v => ({ ...c, lens: lens.key, source: p ? p.source : null, page: p ? p.page : null, verdict: v }))
      })
    )
  }
)

const allClaims = lensResults.flat().filter(Boolean)
const verifiedClaims = allClaims.filter(c => c.verdict && c.verdict.supported)
log(`${allClaims.length} iddia uretildi, ${verifiedClaims.length} dogrulandi.`)

phase('Sentezleme')
const claimsText = verifiedClaims
  .map(c => `- (${c.lens}) ${c.claim} (Kaynak: ${c.source}, s. ${c.page})`)
  .join('\n')

const finalReport = await agent(
  `Sen bir optik kaplama ve malzeme muhendisisin. Asagida, kaynak pasajlara karsi dogrulanmis bulgular listelendi. Bunlara dayanarak "${topic}" konusunda Turkce, akademik dilde bir rapor taslagi uret. SADECE verilen bulgulari kullan, ekleme yapma. Dogrulanmis bulgu yoksa bunu acikca belirt.\n\nDogrulanmis bulgular:\n${claimsText || '(dogrulanmis bulgu yok)'}\n\nCiktiyi giris, bulgular, sonuc metinleri ve kaynakca listesi (kullanilan PDF dosya adlari) olarak yapilandir.`,
  { schema: FINAL_SCHEMA, label: 'final-sentez' }
)

return {
  topic,
  report: finalReport,
  claims_total: allClaims.length,
  claims_verified: verifiedClaims.length,
  sources: [...new Set(verifiedClaims.map(c => c.source).filter(Boolean))],
}
