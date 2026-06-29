# 🐀📡 Radar SOL v2 — multi-fuente

Un radar que vigila a la vez **tres frentes** y te avisa por **Telegram** en cuanto sale algo nuevo que encaja contigo:

1. **Superteam Earn — bounties + projects + hackathons** → lo que de verdad paga (50–16.000+ USDC). Con recompensa, cuánto cierra y **cuánta competencia** tiene.
2. **Superteam Earn — grants** → financiación abierta (rangos en USDC/USDG).
3. **Noticias de airdrops de Solana** → varios feeds RSS, filtrados con precisión para que solo salte con **anuncios reales de airdrop/Solana** (no con el precio ni ETFs).

**Qué hace:** detectar y avisar. **Qué NO hace (a propósito):** no reclama airdrops ni farmea solo — eso te banea (anti-Sybil) y casi todo "auto-claim SOL" es un *drainer*. El trabajo que paga lo haces tú; el radar te dice dónde y cuándo.

---

## Cobertura honesta: qué entra aquí y qué va en el panel

No existe un único grifo que capte **literalmente** todo (los airdrops se cuecen sueltos por Twitter/Discord/blogs). Por eso el sistema es de dos piezas:

- **El radar (esto, automático):** bounties, projects, hackathons, grants y **noticias de airdrops anunciados**. Es lo que sí tiene fuente fiable.
- **El panel (a mano / pasivo):** lo que no se puede "detectar" porque ya corre solo o va tras login:
  - **Grass / Nodle** → ya generan solas 24/7, no hay nada que vigilar.
  - **Quests (Layer3/Galxe) y Learn&Earn (OKX)** → cambian sin parar; se revisan en sus apps.
  - **Posicionarte para airdrops** → usar de verdad Jupiter/Kamino con UNA wallet.

Entre las dos piezas, no se te escapa nada que de verdad importe.

---

## Ponerlo 24/7 gratis (GitHub Actions) — 5 pasos

### 1) Bot de Telegram
- En Telegram abre **@BotFather** → `/newbot` → copia el **token**.
- **Abre tu bot y pulsa "Start"** (mándale algo), si no, no podrá escribirte.

### 2) Tu chat_id
- Abre **@userinfobot** en Telegram → te da tu **Id** (número) = `TELEGRAM_CHAT_ID`.

### 3) Sube los archivos a un repo de GitHub (privado vale)
Mantén la estructura, sobre todo `.github/workflows/radar.yml`:
```
radar-sol/
├─ radar_sol.py
├─ config.json
├─ seen.json
├─ requirements.txt
└─ .github/workflows/radar.yml
```

### 4) Secretos
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 5) Enciéndelo
- Pestaña **Actions** → activa los workflows → **Radar SOL** → **Run workflow**.
- Recibes el mensaje "Radar SOL activado" con el conteo de cada fuente. A partir de ahí corre **solo cada 30 min** y avisa solo lo NUEVO.

---

## Personalizarlo (`config.json`, editable desde el móvil en GitHub)

Cada fuente tiene su bloque con `enabled` (true/false) y filtros:

- **superteam** → `keywords` (en inglés, busca en título/sponsor; vacío `[]` = todo), `min_reward` (número), `types` (`bounty`/`project`/`hackathon`).
- **grants** → `keywords`, `min_reward`. Por defecto te avisa de todos (son pocos y valiosos).
- **news** → `feeds` (URLs RSS) y `keywords` **extra**. El filtro base ya es airdrop+Solana; **no pongas `solana` a secas** o te llegará toda la actualidad. Añade términos muy concretos si quieres (p. ej. el nombre de un proyecto que sigues).

Desactiva una fuente con `"enabled": false`. Los cambios entran en el siguiente ciclo.

---

## Probar en tu ordenador (opcional)
```bash
pip install -r requirements.txt
python radar_sol.py          # modo prueba: imprime por pantalla
# con avisos reales:
export TELEGRAM_BOT_TOKEN="..."; export TELEGRAM_CHAT_ID="..."
python radar_sol.py
```

---

## Notas y límites
- **Solo región Global** en Superteam (la mayoría). Los exclusivos del capítulo España ("La Familia") se ven logueado en superteam.fun/earn; pásate de vez en cuando.
- **Las noticias son un heads-up, no exhaustivo.** Saltan solo con anuncios claros de airdrop/Solana; si está callado, es que no hay nada gordo (filtro de alta precisión, sin spam).
- **Primera ejecución de cada fuente:** siembra en silencio y luego solo avisa lo nuevo. Si añades una fuente más adelante, se siembra sola la primera vez.
- **Anti-flood:** máximo 12 avisos por fuente y ciclo; el resto va en el siguiente.
- **GitHub pausa los cron** tras 60 días sin actividad del repo; si se para, entra en Actions → **Run workflow** (o haz un commit).
- **Seguridad:** el token de Telegram es como una contraseña (va en Secrets, nunca en el código). Y nadie legítimo te pide tu frase semilla de 12 palabras.

---

## ¿Siguiente nivel?
- Que el aviso traiga ya un **borrador inicial** del entregable hecho con IA.
- Script de **auto-staking** para cuando juntes SOL.
- Más fuentes (otras plataformas de bounties, más feeds).

Pídeselo a Claude y lo ampliamos.
