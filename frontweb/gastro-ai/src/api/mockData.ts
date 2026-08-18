import type { SourceRef } from '../types';

interface KnowledgeEntry {
  keywords: string[];
  answer: string;
  sources: SourceRef[];
}

/**
 * This is a small local stand-in for a real RAG pipeline. In production the
 * frontend never reasons about medical content itself — it only sends the
 * user's message to POST /api/chat and renders whatever `answer` and
 * `sources` the retrieval-augmented backend returns. This table exists so
 * the interface can be demoed end-to-end before that backend is connected.
 */
export const KNOWLEDGE_BASE: KnowledgeEntry[] = [
  {
    keywords: ['h. pylori', 'h pylori', 'helicobacter', 'pylori'],
    answer:
      "**Helicobacter pylori (H. pylori)** is a spiral-shaped bacterium that colonizes the stomach lining. It's one of the most common chronic bacterial infections worldwide.\n\n- It weakens the protective mucus layer of the stomach, allowing acid to irritate the tissue underneath.\n- Most infections are acquired in childhood and can persist for decades without symptoms.\n- It's the leading cause of peptic ulcers and is classified as a risk factor for gastric cancer.\n- Diagnosis typically uses a breath test, stool antigen test, or biopsy during endoscopy.\n- Treatment usually involves a combination of antibiotics plus an acid-suppressing medication, often called triple or quadruple therapy.\n\nIf you suspect you may have an H. pylori infection, a healthcare provider can confirm it with the correct test and prescribe an appropriate treatment course.",
    sources: [
      { title: 'H. pylori infection — overview and pathophysiology', url: 'https://www.ncbi.nlm.nih.gov/books/NBK534233/' },
      { title: 'World Gastroenterology Organisation — H. pylori guideline', url: 'https://www.worldgastroenterology.org/guidelines/helicobacter-pylori' },
    ],
  },
  {
    keywords: ['gastritis'],
    answer:
      "**Gastritis** refers to inflammation of the stomach lining. It can be acute (sudden, short-lived) or chronic (developing gradually over time).\n\nCommon causes include:\n- H. pylori infection\n- Long-term use of NSAIDs (like ibuprofen or aspirin)\n- Excessive alcohol consumption\n- Chronic stress or bile reflux\n- Autoimmune conditions\n\nTypical symptoms:\n- Burning or gnawing pain in the upper abdomen\n- Nausea, bloating, or a feeling of fullness after small meals\n- Loss of appetite\n- In some cases, dark stools if there's bleeding\n\nManagement usually focuses on removing the underlying cause (e.g., stopping NSAIDs, treating H. pylori), along with acid-reducing medications to let the lining heal.",
    sources: [
      { title: 'Gastritis: causes, symptoms, and classification', url: 'https://www.niddk.nih.gov/health-information/digestive-diseases/gastritis' },
      { title: 'Chronic gastritis management guideline', url: 'https://www.gastro.org/practice-guidance/gi-patient-center/topic/gastritis' },
    ],
  },
  {
    keywords: ['ulcer', 'peptic ulcer', 'stomach ulcer'],
    answer:
      "**Peptic ulcer disease (PUD)** involves open sores that develop on the inner lining of the stomach (gastric ulcer) or the upper part of the small intestine (duodenal ulcer).\n\nMain causes:\n- H. pylori infection (most common)\n- Long-term NSAID use\n- Rarely, conditions that cause excess acid production\n\nSymptoms:\n- Burning stomach pain, often worse on an empty stomach\n- Pain that may improve temporarily after eating or taking antacids\n- Bloating, nausea, or intolerance to fatty foods\n- Warning signs needing urgent care: vomiting blood, black/tarry stools, or severe sudden pain\n\nDiagnosis is usually confirmed with endoscopy, and treatment combines acid suppression with H. pylori eradication when present.",
    sources: [
      { title: 'Peptic ulcer disease — clinical overview', url: 'https://www.niddk.nih.gov/health-information/digestive-diseases/peptic-ulcers-stomach-ulcers' },
      { title: 'Diagnosis and management of peptic ulcers', url: 'https://www.ncbi.nlm.nih.gov/books/NBK534792/' },
    ],
  },
  {
    keywords: ['gerd', 'acid reflux', 'heartburn', 'reflux'],
    answer:
      "**Gastroesophageal reflux disease (GERD)** occurs when stomach acid regularly flows back into the esophagus, irritating its lining.\n\nWhat causes it:\n- A weakened or relaxed lower esophageal sphincter\n- Hiatal hernia\n- Obesity, pregnancy, or large/fatty meals\n- Smoking and certain medications\n\nCommon symptoms:\n- Heartburn — a burning sensation behind the breastbone\n- Regurgitation of food or sour liquid\n- Difficulty swallowing or a chronic cough\n- Symptoms often worsen when lying down or bending over\n\nManagement typically starts with lifestyle changes (smaller meals, avoiding trigger foods, not lying down soon after eating) plus acid-reducing medication such as a PPI or H2 blocker if symptoms persist.",
    sources: [
      { title: 'GERD — mechanisms and treatment ladder', url: 'https://www.niddk.nih.gov/health-information/digestive-diseases/acid-reflux-ger-gerd-adults' },
      { title: 'ACG Clinical Guideline: GERD', url: 'https://gi.org/guideline/gastroesophageal-reflux-disease/' },
    ],
  },
  {
    keywords: ['dyspepsia', 'indigestion'],
    answer:
      "**Dyspepsia**, commonly called indigestion, is a broad term for persistent discomfort in the upper abdomen rather than a single disease.\n\nIt can present as:\n- Early fullness or bloating after eating\n- Upper abdominal pain or burning\n- Nausea\n\nIt's often categorized as:\n- **Functional (non-ulcer) dyspepsia** — no structural cause found on investigation\n- **Organic dyspepsia** — linked to an identifiable cause such as ulcers, GERD, or H. pylori\n\nEvaluation depends on age and alarm symptoms (unintended weight loss, vomiting, bleeding, difficulty swallowing), which may prompt endoscopy. Otherwise, initial management often includes dietary adjustment and a trial of acid-suppressing medication.",
    sources: [
      { title: 'Functional dyspepsia — diagnosis and care pathway', url: 'https://www.gastrojournal.org/article/S0016-5085(21)03393-8/fulltext' },
    ],
  },
  {
    keywords: ['ibs', 'irritable bowel'],
    answer:
      "**Irritable Bowel Syndrome (IBS)** is a functional gastrointestinal disorder affecting how the gut moves and senses signals, without visible structural damage.\n\nCore features:\n- Recurrent abdominal pain linked to bowel movements\n- Changes in stool frequency or form (diarrhea-predominant, constipation-predominant, or mixed)\n- Bloating and a sense of incomplete evacuation\n\nTriggers commonly include stress, certain foods (like high-FODMAP items), hormonal changes, and gut-brain signaling factors.\n\nManagement is usually individualized: dietary adjustments (e.g., a structured low-FODMAP trial), fiber management, stress-reduction strategies, and medications targeting the dominant symptom pattern.",
    sources: [
      { title: 'IBS — Rome IV diagnostic criteria', url: 'https://theromefoundation.org/rome-iv/rome-iv-criteria/' },
      { title: 'ACG Clinical Guideline: IBS management', url: 'https://gi.org/guideline/irritable-bowel-syndrome/' },
    ],
  },
  {
    keywords: ['ibd', 'crohn', "crohn's", 'colitis', 'inflammatory bowel'],
    answer:
      "**Inflammatory Bowel Disease (IBD)** is an umbrella term for chronic autoimmune-driven inflammation of the digestive tract, primarily encompassing two conditions:\n\n- **Crohn's disease** — can affect any part of the GI tract from mouth to anus, often in patches, and may involve the full thickness of the bowel wall.\n- **Ulcerative colitis** — limited to the colon and rectum, affecting only the innermost lining, typically in a continuous pattern.\n\nShared symptoms include persistent diarrhea (sometimes with blood), abdominal pain, fatigue, and unintended weight loss. Diagnosis relies on a combination of colonoscopy, imaging, and lab markers. Treatment ranges from anti-inflammatory and immune-modulating medications to biologic therapies, tailored to disease severity and location.",
    sources: [
      { title: 'IBD overview: Crohn\u2019s disease vs. ulcerative colitis', url: 'https://www.niddk.nih.gov/health-information/digestive-diseases/crohns-disease' },
      { title: 'Crohn\u2019s & Colitis Foundation — clinical resources', url: 'https://www.crohnscolitisfoundation.org/' },
    ],
  },
  {
    keywords: ['difference between gastritis and an ulcer', 'gastritis vs ulcer', 'gastritis and ulcer'],
    answer:
      "**Gastritis vs. peptic ulcer** — these are related but distinct conditions:\n\n| | Gastritis | Peptic ulcer |\n|---|---|---|\n| What it is | Inflammation of the stomach lining | An open sore through the lining |\n| Depth | Surface-level irritation | Breaks through into deeper tissue |\n| Common causes | H. pylori, NSAIDs, alcohol, stress | H. pylori, NSAIDs (often more prolonged exposure) |\n| Bleeding risk | Usually lower | Higher, especially if untreated |\n| Diagnosis | Endoscopy with biopsy | Endoscopy showing a visible crater |\n\nIn practice, gastritis can progress to an ulcer if the irritation continues untreated, and both share overlapping causes and treatment approaches.",
    sources: [
      { title: 'Gastritis vs. peptic ulcer disease', url: 'https://www.niddk.nih.gov/health-information/digestive-diseases/gastritis' },
    ],
  },
  {
    keywords: ['diet', 'food', 'eat', 'avoid'],
    answer:
      "**General dietary guidance for digestive comfort** (not a substitute for a personalized plan from a dietitian or gastroenterologist):\n\n- Eating smaller, more frequent meals can reduce pressure on the stomach.\n- Common irritants to moderate: caffeine, alcohol, spicy or very fatty foods, and carbonated drinks.\n- Staying upright for 2–3 hours after eating helps if reflux is a concern.\n- Adequate fiber and hydration support regular bowel movements.\n- Keeping a symptom-food diary can help identify personal triggers, since sensitivity varies a lot between individuals.\n\nIf symptoms are frequent or severe, dietary changes alone may not be enough — it's worth discussing with a healthcare professional.",
    sources: [
      { title: 'Dietary approaches to common digestive symptoms', url: 'https://www.niddk.nih.gov/health-information/digestive-diseases/eating-diet-nutrition' },
    ],
  },
];

const FALLBACK_ANSWER =
  "I don't have a specific match for that in my current digestive-health knowledge base yet. I'm focused specifically on stomach and digestive conditions — things like H. pylori, gastritis, peptic ulcers, GERD, dyspepsia, IBS, and inflammatory bowel disease. Could you rephrase your question around one of those areas, or let me know your specific symptom?\n\nFor anything urgent (severe pain, vomiting blood, black stools), please contact a healthcare professional right away rather than waiting on a chat response.";

export function findMockAnswer(message: string): { answer: string; sources: SourceRef[] } {
  const normalized = message.toLowerCase();
  let best: KnowledgeEntry | null = null;
  let bestScore = 0;

  for (const entry of KNOWLEDGE_BASE) {
    const score = entry.keywords.filter((k) => normalized.includes(k)).length;
    if (score > bestScore) {
      bestScore = score;
      best = entry;
    }
  }

  if (best) return { answer: best.answer, sources: best.sources };
  return { answer: FALLBACK_ANSWER, sources: [] };
}

export const SUGGESTED_QUESTIONS = [
  'What is Helicobacter pylori?',
  'What are the symptoms of gastritis?',
  'What causes acid reflux?',
  'What is the difference between gastritis and an ulcer?',
];
