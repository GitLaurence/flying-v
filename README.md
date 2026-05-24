# Flying V — Corporate Website

Official website for **Flying V Petroleum Corporation** (flyingv.com.ph), a Philippine downstream petroleum company operating fuel service stations across Luzon, Visayas, and Mindanao.

## Tech Stack

- **HTML5** — semantic markup, ARIA attributes for accessibility
- **CSS3** — custom properties (design tokens), mobile-first responsive layout, no preprocessor
- **Vanilla JavaScript** — ES5-compatible, no frameworks, no build tools
- **Google Fonts** — Inter (400–800 weight) via `<link>`
- **Zero dependencies** — open any `.html` file directly in a browser

## Pages

| File | Description |
|---|---|
| `index.html` | Homepage — hero, stats strip, products teaser, about snippet, CTA |
| `about.html` | Company story, timeline, mission & vision, core values |
| `products.html` | Fuels (RON 91, RON 95+, Diesel), lubricants, auto services |
| `locations.html` | Station locator with live region & keyword filter |
| `contact.html` | Contact form with validation, office info, business hours |

## Running Locally

No build step required. Open any `.html` file directly in your browser, or use a local server to avoid any asset-path quirks:

```bash
# Python 3 (built-in)
python3 -m http.server 8080

# Node.js (via npx, no install needed)
npx serve .

# VS Code — install the "Live Server" extension, then right-click index.html → "Open with Live Server"
```

Then open `http://localhost:8080` in your browser.

## Project Structure

```
flying-v/
├── index.html            # Homepage
├── about.html            # About the company
├── products.html         # Fuel grades, lubricants, auto services
├── locations.html        # Station locator
├── contact.html          # Contact form + office info
├── css/
│   └── styles.css        # All styles — design tokens, layout, components
├── js/
│   └── main.js           # Navigation, form validation, station filter, scroll effects
├── assets/
│   ├── images/           # Hero images and station photos
│   └── icons/            # SVG icons
└── README.md
```

## Brand & Design

- **Primary color:** `#C8102E` (Flying V red)
- **Accent color:** `#F5A623` (gold/amber)
- **Typography:** Inter (Google Fonts), 8pt spacing scale
- **Style:** Corporate/professional, mobile-first responsive (375px → 768px → 1024px → 1200px)

## Browser Support

Targets modern evergreen browsers — Chrome, Firefox, Safari, Edge. The scroll-reveal feature uses `IntersectionObserver` and degrades gracefully on older browsers (elements simply appear without animation).

## Deployment

Static files — deploy to any host with no build step:

| Platform | Method |
|---|---|
| **GitHub Pages** | Push to `main`, enable Pages in repo Settings → Pages |
| **Netlify** | Drag-and-drop the project folder at app.netlify.com |
| **Vercel** | Connect the repo; framework preset: "Other" |
| **Traditional hosting** | FTP the entire folder contents to `public_html/` |

## Adding Real Content

Before going live, replace the following placeholders:

- **Logo** — add `assets/images/logo.svg` and update `.site-header__logo` markup
- **Hero images** — add photos to `assets/images/` and reference them via CSS `background-image` on `.hero` and `.page-hero`
- **Contact details** — update phone numbers, address, and email across all pages
- **Google Maps** — replace the map placeholder in `contact.html` with an actual `<iframe>` embed
- **Station data** — expand the station cards in `locations.html` with real addresses and hours

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit your changes with a descriptive message
4. Open a Pull Request against `main`
