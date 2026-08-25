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
    value: 'meta/llama-3.3-70b-instruct',
    label: 'Meta Llama 3.3 70B Instruct',
    badge: '⭐ Recomendado por defecto',
    badgeClass: 'bg-green-500/20 text-green-400 border-green-500/40',
    description: 'El mejor modelo general para conversión de audiolibros. Excelente fidelidad narrativa, comprensión de personajes y formato JSON estricto.',
    specs: '70B Parámetros • Contexto 128k • Máxima calidad',
    freeTier: true,
  },
  {
    value: 'nvidia/llama-3.1-nemotron-70b-instruct',
    label: 'NVIDIA Nemotron 70B Instruct',
    badge: '⚡ Optimizado NVIDIA',
    badgeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    description: 'Afinado por NVIDIA con alineación RLHF avanzada para máxima precisión en diálogos y roles complejos.',
    specs: '70B Parámetros • Optimizado TensorRT-LLM',
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
    value: 'qwen/qwen2.5-72b-instruct',
    label: 'Qwen 2.5 72B Instruct',
    badge: '📚 Análisis Literario',
    badgeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    description: 'Uno de los modelos más potentes del mundo en análisis de novelas extensas y distinción de múltiples voces secundarias.',
    specs: '72B Parámetros • Vocabulario enriquecido • Alibaba Cloud',
    freeTier: true,
  },
  {
    value: 'meta/llama-3.1-8b-instruct',
    label: 'Meta Llama 3.1 8B Instruct',
    badge: '⚡ Ultra Rápido',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    description: 'Modelo ligero con respuesta instantánea. Ideal para libros con estructura sencilla o cuando buscas máxima velocidad.',
    specs: '8B Parámetros • Tiempo de respuesta ultra bajo',
    freeTier: true,
  },
  {
    value: 'deepseek-ai/deepseek-r1',
    label: 'DeepSeek R1 (Reasoning)',
    badge: '🧠 Razonamiento Profundo',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    description: 'Modelo con cadena de pensamiento paso a paso. Deduce con precisión quién habla en diálogos confusos o sin acotaciones explícitas.',
    specs: '671B MoE • Chain-of-Thought • DeepSeek AI',
    freeTier: true,
  },
  {
    value: 'deepseek-ai/deepseek-v3',
    label: 'DeepSeek V3',
    badge: '🚀 Alta Capacidad',
    badgeClass: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/40',
    description: 'Arquitectura Mixture-of-Experts de última generación con alto rendimiento y gran velocidad de procesamiento.',
    specs: '671B MoE (37B activos) • 64k Contexto',
    freeTier: true,
  },
  {
    value: 'google/gemma-2-27b-it',
    label: 'Google Gemma 2 27B Instruct',
    badge: '✨ Google Gemma 2',
    badgeClass: 'bg-sky-500/20 text-sky-400 border-sky-500/40',
    description: 'Arquitectura eficiente diseñada por Google DeepMind con gran sensibilidad poética y fluidez estilística.',
    specs: '27B Parámetros • Google DeepMind',
    freeTier: true,
  },
  {
    value: 'mistralai/mixtral-8x22b-instruct-v0.1',
    label: 'Mixtral 8x22B Instruct',
    badge: '⚖️ Mixture of Experts',
    badgeClass: 'bg-teal-500/20 text-teal-400 border-teal-500/40',
    description: 'Modelo MoE muy equilibrado con gran capacidad de generalización literaria.',
    specs: '176B Total • Mistral AI',
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
  {
    value: 'deepseek/deepseek-chat-v3-0324:free',
    label: 'DeepSeek V3 (Free)',
    badge: '⭐ Recomendado Free',
    badgeClass: 'bg-green-500/20 text-green-400 border-green-500/40',
    description: 'Excelente modelo gratuito en OpenRouter para procesamiento de diálogos y análisis.',
    specs: 'Free Tier • DeepSeek AI',
    freeTier: true,
  },
  {
    value: 'meta-llama/llama-3.3-70b-instruct:free',
    label: 'Meta Llama 3.3 70B (Free)',
    badge: '⭐ Llama 3.3 Free',
    badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    description: 'Versión gratuita del modelo 70B de Meta con alto rendimiento general.',
    specs: '70B • Free Tier • Meta',
    freeTier: true,
  },
  {
    value: 'google/gemini-2.0-flash-exp:free',
    label: 'Google Gemini 2.0 Flash (Free)',
    badge: '⚡ Ultra Rápido Free',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    description: 'Procesamiento instantáneo en la capa gratuita experimental de Google.',
    specs: 'Free Tier • Google',
    freeTier: true,
  },
  {
    value: 'qwen/qwen-2.5-72b-instruct:free',
    label: 'Qwen 2.5 72B (Free)',
    badge: '📚 Análisis Literario Free',
    badgeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    description: 'Gran comprensión lectora en español y seguimiento de formato.',
    specs: '72B • Free Tier • Alibaba Cloud',
    freeTier: true,
  },
  {
    value: 'anthropic/claude-3.5-sonnet',
    label: 'Anthropic Claude 3.5 Sonnet',
    badge: '🏆 Prémium',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    description: 'La referencia en la industria para análisis de texto y literatura de alta complejidad.',
    specs: 'Requiere saldo en OpenRouter • Anthropic',
    freeTier: false,
  },
]

export const GEMINI_MODELS: ModelCatalogItem[] = [
  {
    value: 'gemini-2.5-flash',
    label: 'Gemini 2.5 Flash',
    badge: '⭐ Recomendado Google',
    badgeClass: 'bg-green-500/20 text-green-400 border-green-500/40',
    description: 'Rápido, preciso, con gran ventana de contexto y generoso límite de peticiones gratuitas.',
    specs: 'Google AI Studio • Cuota Free Generosa',
    freeTier: true,
  },
  {
    value: 'gemini-2.5-pro',
    label: 'Gemini 2.5 Pro',
    badge: '🧠 Razonamiento Máximo',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    description: 'Capacidad de razonamiento superior para obras complejas o con muchos personajes secundarios.',
    specs: 'Google AI Studio • Máximo contexto y razonamiento',
    freeTier: true,
  },
  {
    value: 'gemini-2.0-flash',
    label: 'Gemini 2.0 Flash',
    badge: '⚡ Ultra Baja Latencia',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    description: 'Latencia reducida al mínimo ideal para procesamiento ágil.',
    specs: 'Google AI Studio • Velocidad optimizada',
    freeTier: true,
  },
]

export const OLLAMA_MODELS: ModelCatalogItem[] = [
  {
    value: 'qwen2.5:7b',
    label: 'Qwen 2.5 7B',
    badge: '⭐ Recomendado Local',
    badgeClass: 'bg-green-500/20 text-green-400 border-green-500/40',
    description: 'Óptimo para la mayoría de ordenadores locales con 8GB-16GB RAM/VRAM.',
    specs: '7B Parámetros • Local 100% Offline',
    freeTier: true,
  },
  {
    value: 'llama3.3:70b',
    label: 'Llama 3.3 70B',
    badge: '🏆 Calidad Máxima Local',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    description: 'Máxima calidad local. Requiere GPU con 24GB+ de VRAM o servidor local potente.',
    specs: '70B Parámetros • Alta exigencia de hardware',
    freeTier: true,
  },
  {
    value: 'llama3.1:8b',
    label: 'Llama 3.1 8B',
    badge: '⚡ Ligero y Veloz',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    description: 'Rápido y con bajo consumo de memoria. Apto para cualquier equipo estándar.',
    specs: '8B Parámetros • Ligero y eficiente',
    freeTier: true,
  },
  {
    value: 'mistral:7b',
    label: 'Mistral 7B',
    badge: '📘 Clásico Local',
    badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    description: 'Excelente estabilidad y fidelidad en ejecución local.',
    specs: '7B Parámetros • Mistral AI',
    freeTier: true,
  },
  {
    value: 'gemma2:9b',
    label: 'Google Gemma 2 9B',
    badge: '✨ Gemma 2 Local',
    badgeClass: 'bg-sky-500/20 text-sky-400 border-sky-500/40',
    description: 'Modelo eficiente de Google para ejecución local con buena sensibilidad literaria.',
    specs: '9B Parámetros • Google',
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
