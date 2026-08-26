/* Ferramenta de tradução — textos da interface e dos conteúdos */

const LANGS = [
  { code: "pt", label: "Português", flag: "PT" },
  { code: "en", label: "English",   flag: "EN" },
  { code: "es", label: "Español",   flag: "ES" }
];

const UI = {
  pt: {
    search: "Eventos perto de mim", main: "Principais notícias", events: "Eventos na região",
    allCities: "Toda a região", chooseCity: "Escolha a cidade", agenda: "Agenda", noEvents: "Nenhum evento neste dia", reminder: "Lembrete de evento", warnMe: "Avisar antes de começar", eventAhead: "evento salvo ainda por vir", eventsAhead: "eventos salvos ainda por vir", noneAhead: "nenhum evento salvo ainda por vir",
    updates: "Atualizações da região", swipe: "deslize →", home: "Início", map: "Mapa", profile: "Perfil",
    mapHint: "Só aparecem notícias com local confirmado", news: "Notícia", event: "Evento",
    saved: "Salvos", savedNews: "Notícias", savedEvents: "Eventos",
    receive: "O que você quer receber", interests: "Seus interesses", guideAgain: "Rever o guia do app",
    authCta: "Entre ou cadastre-se", visitor: "Visitante", visitorSub: "Entre para salvar e personalizar",
    readAt: "Ler na fonte", openSource: "Abrir matéria completa", save: "Salvar", saved2: "Salvo",
    remove: "Remover", relatedTitle: "Leia também", emptyNews: "Nenhuma notícia salva ainda.",
    emptyEvents: "Nenhum evento salvo ainda.", emptyFeed: "Nada encontrado para esta busca.",
    signin: "Entrar", signup: "Cadastrar", email: "E-mail", cont: "continuar", source: "Fonte",
    langTitle: "Idioma da interface", translated: "traduzido automaticamente"
  },
  en: {
    search: "Events near me", main: "Top stories", events: "Events nearby",
    allCities: "Whole region", chooseCity: "Choose a city", agenda: "Agenda", noEvents: "No events on this day", reminder: "Event reminder", warnMe: "Notify me before it starts", eventAhead: "saved event coming up", eventsAhead: "saved events coming up", noneAhead: "no saved events coming up",
    updates: "Regional updates", swipe: "swipe →", home: "Home", map: "Map", profile: "Profile",
    mapHint: "Only stories with a confirmed location", news: "Story", event: "Event",
    saved: "Saved", savedNews: "News", savedEvents: "Events",
    receive: "What you want to receive", interests: "Your interests", guideAgain: "See the app guide again",
    authCta: "Sign in or sign up", visitor: "Guest", visitorSub: "Sign in to save and personalize",
    readAt: "Read at source", openSource: "Open full story", save: "Save", saved2: "Saved",
    remove: "Remove", relatedTitle: "Read next", emptyNews: "No saved stories yet.",
    emptyEvents: "No saved events yet.", emptyFeed: "Nothing found for this search.",
    signin: "Sign in", signup: "Sign up", email: "E-mail", cont: "continue", source: "Source",
    langTitle: "Interface language", translated: "machine translated"
  },
  es: {
    search: "Eventos cerca de mí", main: "Noticias principales", events: "Eventos en la región",
    allCities: "Toda la región", chooseCity: "Elige la ciudad", agenda: "Agenda", noEvents: "Ningún evento este día", reminder: "Recordatorio de evento", warnMe: "Avisarme antes de empezar", eventAhead: "evento guardado por venir", eventsAhead: "eventos guardados por venir", noneAhead: "ningún evento guardado por venir",
    updates: "Actualizaciones de la región", swipe: "desliza →", home: "Inicio", map: "Mapa", profile: "Perfil",
    mapHint: "Solo noticias con lugar confirmado", news: "Noticia", event: "Evento",
    saved: "Guardados", savedNews: "Noticias", savedEvents: "Eventos",
    receive: "Qué quieres recibir", interests: "Tus intereses", guideAgain: "Ver la guía otra vez",
    authCta: "Entra o regístrate", visitor: "Visitante", visitorSub: "Entra para guardar y personalizar",
    readAt: "Leer en la fuente", openSource: "Abrir nota completa", save: "Guardar", saved2: "Guardado",
    remove: "Quitar", relatedTitle: "Lee también", emptyNews: "Aún no hay noticias guardadas.",
    emptyEvents: "Aún no hay eventos guardados.", emptyFeed: "No se encontró nada para esta búsqueda.",
    signin: "Entrar", signup: "Registrarse", email: "Correo", cont: "continuar", source: "Fuente",
    langTitle: "Idioma de la interfaz", translated: "traducido automáticamente"
  }
};

/* categorias */
const CATS_I18N = {
  en: { Todos: "All", Show: "Concerts", Festival: "Festivals", Esporte: "Sports", Cultura: "Culture", Cidade: "City", Gastronomia: "Food" },
  es: { Todos: "Todos", Show: "Conciertos", Festival: "Festivales", Esporte: "Deportes", Cultura: "Cultura", Cidade: "Ciudad", Gastronomia: "Gastronomía" }
};

/* títulos e resumos traduzidos dos conteúdos */
const CONTENT_I18N = {
  en: {
    n1: ["Lollapalooza is coming to Ribeirão Preto", "For the first time outside the capital, the festival sets up three stages at the Parque Permanente in November."],
    n2: ["Theatro Pedro II reopens main hall after restoration", "A ten-month project restored the ceiling, the acoustics and the original seats of the 1930 hall."],
    n3: ["Independência Avenue gets a new bike lane", "The 4.2 km stretch links the USP campus to downtown and should open in September."],
    n4: ["Farmers market returns to Bosque on Sundays", "Thirty stands from regional family farms gather at Bosque Municipal starting this Sunday."],
    n5: ["Choperia hosts a marathon of local rock", "Twelve bands take turns on two stages during the cultural night at Choperia Pinguim."],
    n6: ["Coffee Museum opens digital archive with 12,000 photos", "Images of the region's coffee cycle are now free to browse online."],
    e1: ["Lollapalooza RP", "Two days, three stages and more than 30 national and international acts."],
    e2: ["Reopening concert", "The municipal symphony marks the return of the main hall, free entry."],
    e3: ["Farmers market", "Thirty family-farm stands, live cooking and a kids area."],
    e4: ["Local rock marathon", "Twelve regional bands on two stages until dawn."],
    e5: ["Poetry night at Praça XV", "Poetry, samba circle and a zine fair in the historic center."]
  },
  es: {
    n1: ["Lollapalooza llega a Ribeirão Preto", "Por primera vez fuera de la capital, el festival monta tres escenarios en el Parque Permanente en noviembre."],
    n2: ["Theatro Pedro II reabre su sala principal tras la restauración", "Una obra de diez meses recuperó el cielorraso, la acústica y las butacas originales de 1930."],
    n3: ["La Avenida Independência estrena ciclovía", "El tramo de 4,2 km une el campus de la USP con el centro y se entrega en septiembre."],
    n4: ["La feria de productores vuelve al Bosque los domingos", "Treinta puestos de agricultura familiar se reúnen en el Bosque Municipal desde este domingo."],
    n5: ["La Choperia recibe una maratón de rock local", "Doce bandas se alternan en dos escenarios durante la noche cultural."],
    n6: ["El Museo del Café abre un archivo digital con 12 mil fotos", "Imágenes del ciclo cafetero de la región ya se pueden consultar gratis en línea."],
    e1: ["Lollapalooza RP", "Dos días, tres escenarios y más de 30 artistas nacionales e internacionales."],
    e2: ["Concierto de reapertura", "La sinfónica municipal marca el regreso de la sala principal, entrada gratuita."],
    e3: ["Feria de productores", "Treinta puestos de agricultura familiar, cocina en vivo y área infantil."],
    e4: ["Maratón de rock local", "Doce bandas de la región en dos escenarios hasta la madrugada."],
    e5: ["Velada poética en la Praça XV", "Poesía, rueda de samba y feria de fanzines en el centro histórico."]
  }
};
