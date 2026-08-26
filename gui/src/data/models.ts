export interface ModelCatalogItem {
  value: string
  label: string
  badge: string
  badgeClass: string
  description: string
  specs: string
  freeTier: boolean
}

export const NIM_MODELS: ModelCatalogItem[] = [
  {
    value: 'nvidia/llama-3.1-nemotron-70b-instruct',
    label: 'NVIDIA Nemotron 70B Instruct',
    badge: '⭐ Recomendado por defecto',
    badgeClass: 'bg-green-500/20 text-green-400 border-green-500/40',
    description: 'Afinado por NVIDIA con alineación RLHF avanzada para máxima fidelidad narrativa, comprensión de personajes y formato JSON estricto.',
    specs: '70B Parámetros • Optimizado TensorRT-LLM • NVIDIA',
    freeTier: true,
  },
  {
    value: 'mistralai/mistral-large-2-instruct',
    label: 'Mistral Large 2 (123B)',
    badge: '🌐 Excelente en Español',
    badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    description: 'Excelente dominio de la literatura clásica y contemporánea en español. Gran capacidad para capturar tonos emocionales y subtextos.',
    specs: '123B Parámetros • Contexto 128k • Mistral AI',
    freeTier: true,
  },
  {
    value: 'google/gemma-3-12b-it',
    label: 'Google Gemma 3 12B Instruct',
    badge: '⚡ Ultra Rápido',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    description: 'Modelo ligero de última generación de Google. Respuesta rápida e ideal para libros estándar y novelas cortas.',
    specs: '12B Parámetros • Google DeepMind',
    freeTier: true,
  },
  {
    value: 'mistralai/mixtral-8x22b-v0.1',
    label: 'Mixtral 8x22B',
    badge: '⚖️ Mixture of Experts',
    badgeClass: 'bg-teal-500/20 text-teal-400 border-teal-500/40',
    description: 'Modelo MoE muy equilibrado con gran capacidad de generalización literaria.',
    specs: '176B Total • Mistral AI',
    freeTier: true,
  },
  {
    value: 'openai/gpt-oss-120b',
    label: 'OpenAI GPT-OSS 120B',
    badge: '🚀 Gran Capacidad',
    badgeClass: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/40',
    description: 'Modelo masivo de código abierto para análisis literario complejo y distinción de personajes.',
    specs: '120B Parámetros • Alto Razonamiento',
    freeTier: true,
  },
  {
    value: '01-ai/yi-large',
    label: '01.AI Yi-Large',
    badge: '📚 Análisis Literario',
    badgeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    description: 'Modelo de gran escala con excelente comprensión semántica y análisis de historias extensas.',
    specs: 'Yi-Large • Contexto 32k',
    freeTier: true,
  },
  {
    value: 'writer/palmyra-creative-122b',
    label: 'Palmyra Creative 122B',
    badge: '📖 Narrativa Creativa',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    description: 'Especializado en narración literaria, prosodia y comprensión emocional de diálogos dramáticos.',
    specs: '122B Parámetros • Writer AI',
    freeTier: true,
  },
  {
    value: 'moonshotai/kimi-k2.6',
    label: 'Moonshot Kimi K2.6',
    badge: '📜 Contexto Extenso',
    badgeClass: 'bg-rose-500/20 text-rose-400 border-rose-500/40',
    description: 'Especializado en mantener la consistencia de personajes a lo largo de capítulos muy extensos.',
    specs: 'Moonshot AI • Larga ventana de contexto',
    freeTier: true,
  },
  {
    value: 'minimaxai/minimax-m3',
    label: 'MiniMax M3',
    badge: '🎯 Diálogos Conversacionales',
    badgeClass: 'bg-violet-500/20 text-violet-400 border-violet-500/40',
    description: 'Enfoque avanzado en procesamiento de diálogos y patrones conversacionales.',
    specs: 'MiniMax AI • Alta coherencia dialógica',
    freeTier: true,
  },
]

export const OPENROUTER_MODELS: ModelCatalogItem[] = [
  // --- FREE TIER MODELS ---
  {
    value: 'nvidia/nemotron-3-ultra-550b-a55b:free',
    label: 'NVIDIA Nemotron 3 Ultra (Free)',
    badge: '⭐ Flagship Free',
    badgeClass: 'bg-green-500/20 text-green-400 border-green-500/40',
    description: 'Modelo MoE frontier de razonamiento de NVIDIA con 550B parámetros. Máxima fidelidad en análisis literario.',
    specs: '550B MoE • Contexto 1M • Free Tier',
    freeTier: true,
  },
  {
    value: 'nvidia/nemotron-3-super-120b-a12b:free',
    label: 'NVIDIA Nemotron 3 Super (Free)',
    badge: '⚡ Alta Potencia Free',
    badgeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    description: 'Gran balance de velocidad y coherencia narrativa en diálogos complejos de novelas.',
    specs: '120B Parámetros • Free Tier',
    freeTier: true,
  },
  {
    value: 'nvidia/nemotron-3.5-lightning:free',
    label: 'NVIDIA Nemotron 3.5 Lightning (Free)',
    badge: '🚀 Ultra Rápido Free',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    description: 'Tiempo de respuesta ultrarrápido ideal para procesamiento ágil y fluido de libros largos.',
    specs: '30B Parámetros • Free Tier',
    freeTier: true,
  },
  {
    value: 'minimax/minimax-m3:free',
    label: 'MiniMax M3 (Free)',
    badge: '🎯 Diálogos Free',
    badgeClass: 'bg-violet-500/20 text-violet-400 border-violet-500/40',
    description: 'Excelente modelado de patrones conversacionales y modismos de personajes secundarios.',
    specs: 'MiniMax AI • Free Tier',
    freeTier: true,
  },
  {
    value: 'minimax/minimax-m2.7:free',
    label: 'MiniMax M2.7 (Free)',
    badge: '💬 Conversacional Free',
    badgeClass: 'bg-fuchsia-500/20 text-fuchsia-400 border-fuchsia-500/40',
    description: 'Modelo optimizado para deducción de tono y sentimiento de diálogos dramáticos.',
    specs: 'MiniMax AI • Free Tier',
    freeTier: true,
  },
  {
    value: 'z-ai/glm-5.2:free',
    label: 'Z.ai GLM 5.2 (Free)',
    badge: '📜 Contexto Extenso Free',
    badgeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    description: 'Ventana de contexto amplia y gran adherencia a formatos de atribución JSON.',
    specs: '1M Contexto • Free Tier',
    freeTier: true,
  },
  {
    value: 'google/gemma-4-31b-it:free',
    label: 'Google Gemma 4 31B (Free)',
    badge: '✨ Google Gemma 4 Free',
    badgeClass: 'bg-sky-500/20 text-sky-400 border-sky-500/40',
    description: 'Arquitectura de última generación de Google DeepMind con gran sensibilidad poética y literaria.',
    specs: '31B Parámetros • Google DeepMind • Free Tier',
    freeTier: true,
  },
  {
    value: 'google/gemma-4-26b-a4b-it:free',
    label: 'Google Gemma 4 26B MoE (Free)',
    badge: '⚖️ Gemma MoE Free',
    badgeClass: 'bg-teal-500/20 text-teal-400 border-teal-500/40',
    description: 'Modelo eficiente Mixture of Experts con respuesta rápida y bajo consumo de tokens.',
    specs: '26B MoE • Google DeepMind • Free Tier',
    freeTier: true,
  },
  {
    value: 'thinkingmachines/inkling:free',
    label: 'ThinkingMachines Inkling (Free)',
    badge: '🧠 Razonamiento Free',
    badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    description: 'Modelo open-weight de gran capacidad para deducción analítica de roles y narración.',
    specs: '41B Activos • Free Tier',
    freeTier: true,
  },
  {
    value: 'poolside/laguna-s-2.1:free',
    label: 'Poolside Laguna S 2.1 (Free)',
    badge: '🛠️ Precisión Estructural Free',
    badgeClass: 'bg-rose-500/20 text-rose-400 border-rose-500/40',
    description: 'Gran solidez en generación estructurada y estricto formateo de esquemas JSON.',
    specs: '118B Total • Free Tier',
    freeTier: true,
  },

  // --- PREMIUM MODELS ---
  {
    value: 'anthropic/claude-3.5-sonnet',
    label: 'Anthropic Claude 3.5 Sonnet',
    badge: '👑 Oro Literario (Prémium)',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    description: 'La máxima referencia en la industria para comprensión de literatura, subtextos y personajes complejos.',
    specs: 'Anthropic • Requiere saldo OpenRouter',
    freeTier: false,
  },
  {
    value: 'openai/gpt-4o',
    label: 'OpenAI GPT-4o',
    badge: '🚀 OpenAI GPT-4o (Prémium)',
    badgeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    description: 'Modelo insignia de OpenAI con alta velocidad y profunda inteligencia multimodal y literaria.',
    specs: 'OpenAI • Requiere saldo OpenRouter',
    freeTier: false,
  },
  {
    value: 'deepseek/deepseek-r1',
    label: 'DeepSeek R1 (Prémium)',
    badge: '🧠 Razonamiento Profundo (Prémium)',
    badgeClass: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/40',
    description: 'Cadena de pensamiento exhaustiva para deducir quién habla en pasajes confusos o sin narrador explícito.',
    specs: 'DeepSeek AI • Requiere saldo OpenRouter',
    freeTier: false,
  },
  {
    value: 'meta-llama/llama-3.3-70b-instruct',
    label: 'Meta Llama 3.3 70B (Prémium)',
    badge: '⭐ Meta Llama 3.3 (Prémium)',
    badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    description: 'Excelente fidelidad narrativa y comprensión de roles y acentos literarios.',
    specs: '70B Parámetros • Meta • Requiere saldo OpenRouter',
    freeTier: false,
  },
  {
    value: 'qwen/qwen-2.5-72b-instruct',
    label: 'Qwen 2.5 72B (Prémium)',
    badge: '📚 Gran Escala (Prémium)',
    badgeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    description: 'Potente modelo multilingüe con extraordinario dominio de obras en español.',
    specs: '72B Parámetros • Alibaba Cloud • Requiere saldo OpenRouter',
    freeTier: false,
  },
]

export const GEMINI_MODELS: ModelCatalogItem[] = [
  {
    value: 'gemini-2.0-flash',
    label: 'Google Gemini 2.0 Flash',
    badge: '⭐ Recomendado Free',
    badgeClass: 'bg-green-500/20 text-green-400 border-green-500/40',
    description: 'Rápido, ultra preciso, con gran ventana de contexto y generoso límite de peticiones gratuitas en Google AI Studio.',
    specs: 'Google AI Studio • Cuota Free Generosa (15 RPM)',
    freeTier: true,
  },
  {
    value: 'gemini-1.5-flash',
    label: 'Google Gemini 1.5 Flash',
    badge: '⚡ Ultra Baja Latencia',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    description: 'Procesamiento veloz con excelente adherencia a esquemas JSON y contexto de 1M tokens.',
    specs: 'Google AI Studio • Velocidad optimizada',
    freeTier: true,
  },
  {
    value: 'gemini-1.5-pro',
    label: 'Google Gemini 1.5 Pro',
    badge: '🧠 Razonamiento Máximo',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    description: 'Capacidad de razonamiento superior para obras complejas o novelas con muchos personajes secundarios.',
    specs: 'Google AI Studio • 2M Contexto • Razonamiento Avanzado',
    freeTier: false,
  },
]

export const OLLAMA_MODELS: ModelCatalogItem[] = [
  {
    value: 'qwen2.5:7b',
    label: 'Qwen 2.5 7B',
    badge: '⭐ Recomendado Local',
    badgeClass: 'bg-green-500/20 text-green-400 border-green-500/40',
    description: 'Óptimo para la mayoría de ordenadores locales con 8GB-16GB RAM/VRAM. 100% gratuito y privado.',
    specs: '7B Parámetros • Local 100% Offline • Free',
    freeTier: true,
  },
  {
    value: 'llama3.3:70b',
    label: 'Llama 3.3 70B',
    badge: '🏆 Calidad Máxima Local',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    description: 'Máxima calidad local. Requiere GPU con 24GB+ de VRAM o servidor local potente.',
    specs: '70B Parámetros • Alta exigencia de hardware • Free',
    freeTier: true,
  },
  {
    value: 'llama3.1:8b',
    label: 'Llama 3.1 8B',
    badge: '⚡ Ligero y Veloz',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    description: 'Rápido y con bajo consumo de memoria. Apto para cualquier equipo estándar.',
    specs: '8B Parámetros • Ligero y eficiente • Free',
    freeTier: true,
  },
  {
    value: 'mistral:7b',
    label: 'Mistral 7B',
    badge: '📘 Clásico Local',
    badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    description: 'Excelente estabilidad y fidelidad en ejecución local.',
    specs: '7B Parámetros • Mistral AI • Free',
    freeTier: true,
  },
  {
    value: 'gemma2:9b',
    label: 'Google Gemma 2 9B',
    badge: '✨ Gemma 2 Local',
    badgeClass: 'bg-sky-500/20 text-sky-400 border-sky-500/40',
    description: 'Modelo eficiente de Google para ejecución local con buena sensibilidad literaria.',
    specs: '9B Parámetros • Google • Free',
    freeTier: true,
  },
]

export function getModelInfo(provider: string, modelId: string): ModelCatalogItem | undefined {
  let list: ModelCatalogItem[] = []
  if (provider === 'nim') list = NIM_MODELS
  else if (provider === 'openrouter') list = OPENROUTER_MODELS
  else if (provider === 'gemini') list = GEMINI_MODELS
  else if (provider === 'ollama') list = OLLAMA_MODELS

  return list.find((m) => m.value === modelId)
}
