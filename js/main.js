(function () {
  'use strict';

  // Coalesce a scroll handler to at most once per animation frame, so
  // layout-reading handlers (getBoundingClientRect, offsetHeight, …) don't
  // run on every native scroll tick.
  function rafThrottle(fn) {
    var ticking = false;
    return function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () {
        fn();
        ticking = false;
      });
    };
  }

  // ─── 1. STICKY HEADER ────────────────────────────────────────────────────────
  function initStickyHeader() {
    var header = document.getElementById('site-header');
    if (!header) return;

    var isHomePage = document.body.classList.contains('page-home');
    var THRESHOLD = 60;

    function onScroll() {
      var scrolled = window.scrollY > THRESHOLD;
      header.classList.toggle('is-scrolled', scrolled);
      if (isHomePage) {
        header.classList.toggle('is-transparent', !scrolled);
      }
    }

    if (isHomePage) header.classList.add('is-transparent');
    window.addEventListener('scroll', rafThrottle(onScroll), { passive: true });
    onScroll();
  }

  // ─── 2. MOBILE MENU ──────────────────────────────────────────────────────────
  function initMobileMenu() {
    var hamburger = document.getElementById('hamburger');
    var nav       = document.getElementById('site-nav');
    if (!hamburger || !nav) return;

    function setOpen(open) {
      var wasOpen = hamburger.classList.contains('is-open');
      hamburger.classList.toggle('is-open', open);
      nav.classList.toggle('is-open', open);
      hamburger.setAttribute('aria-expanded', String(open));
      document.body.style.overflow = open ? 'hidden' : '';

      if (open) {
        var firstLink = nav.querySelector('.site-nav__link');
        if (firstLink) firstLink.focus();
      } else if (wasOpen && nav.contains(document.activeElement)) {
        // Only steal focus back if it was inside the panel we're closing —
        // avoids yanking focus on e.g. the >=768px resize auto-close.
        hamburger.focus();
      }
    }

    hamburger.addEventListener('click', function () {
      setOpen(!hamburger.classList.contains('is-open'));
    });

    nav.querySelectorAll('.site-nav__link').forEach(function (link) {
      link.addEventListener('click', function () { setOpen(false); });
    });

    document.addEventListener('click', function (e) {
      if (hamburger.classList.contains('is-open') &&
          !nav.contains(e.target) &&
          !hamburger.contains(e.target)) {
        setOpen(false);
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { setOpen(false); return; }

      if (e.key === 'Tab' && hamburger.classList.contains('is-open')) {
        var focusable = nav.querySelectorAll('a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (!focusable.length) return;
        var first = focusable[0];
        var last  = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth >= 768) setOpen(false);
    });
  }

  // ─── 3. ACTIVE NAV LINK ──────────────────────────────────────────────────────
  function initActiveNav() {
    var current = document.body.dataset.page;
    document.querySelectorAll('.site-nav__link').forEach(function (link) {
      if (link.dataset.page === current) {
        link.classList.add('is-active');
        link.setAttribute('aria-current', 'page');
      }
    });
  }

  // ─── 4. SMOOTH SCROLL ────────────────────────────────────────────────────────
  function initSmoothScroll() {
    var reduceMotion = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
      anchor.addEventListener('click', function (e) {
        var id = this.getAttribute('href');
        if (id === '#') return;
        var target = document.querySelector(id);
        if (!target) return;
        e.preventDefault();
        var header = document.getElementById('site-header');
        var offset = header ? header.offsetHeight : 0;
        var top = target.getBoundingClientRect().top + window.scrollY - offset - 16;
        window.scrollTo({ top: top, behavior: reduceMotion ? 'auto' : 'smooth' });
      });
    });
  }

  // ─── 5. FOOTER YEAR ──────────────────────────────────────────────────────────
  function initFooterYear() {
    var el = document.getElementById('footer-year');
    if (el) el.textContent = new Date().getFullYear();
  }

  // ─── 6. CONTACT FORM VALIDATION ──────────────────────────────────────────────
  function initContactForm() {
    var form = document.getElementById('contact-form');
    if (!form) return;

    var fields = {
      name: {
        el:  document.getElementById('f-name'),
        err: document.getElementById('f-name-error'),
        check: function (v) {
          if (!v.trim())           return 'Full name is required.';
          if (v.trim().length < 2) return 'Name must be at least 2 characters.';
          return '';
        }
      },
      email: {
        el:  document.getElementById('f-email'),
        err: document.getElementById('f-email-error'),
        check: function (v) {
          if (!v.trim()) return 'Email address is required.';
          if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim())) return 'Please enter a valid email address.';
          return '';
        }
      },
      subject: {
        el:  document.getElementById('f-subject'),
        err: document.getElementById('f-subject-error'),
        check: function (v) {
          if (!v) return 'Please select a subject.';
          return '';
        }
      },
      message: {
        el:  document.getElementById('f-message'),
        err: document.getElementById('f-message-error'),
        check: function (v) {
          if (!v.trim())            return 'Message is required.';
          if (v.trim().length < 20) return 'Message must be at least 20 characters.';
          return '';
        }
      }
    };

    function validateField(key) {
      var f   = fields[key];
      if (!f.el) return true;
      var msg = f.check(f.el.value);
      if (f.err) f.err.textContent = msg;
      f.el.classList.toggle('is-invalid', !!msg);
      return !msg;
    }

    Object.keys(fields).forEach(function (key) {
      var f = fields[key];
      if (!f.el) return;
      f.el.addEventListener('blur',  function () { validateField(key); });
      f.el.addEventListener('input', function () {
        if (f.el.classList.contains('is-invalid')) validateField(key);
      });
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var valid = Object.keys(fields).map(validateField).every(Boolean);
      if (!valid) {
        var first = form.querySelector('.is-invalid');
        if (first) first.focus();
        return;
      }
      var btn = document.getElementById('btn-submit');
      if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
      setTimeout(function () {
        form.reset();
        form.style.display = 'none';
        var success = document.getElementById('form-success');
        if (success) success.hidden = false;
      }, 1200);
    });
  }

  // ─── 7. STATION LOCATOR ──────────────────────────────────────────────────────
  function initStationLocator() {
    var grid      = document.getElementById('station-grid');
    var emptyEl   = document.getElementById('locator-empty');
    var countEl   = document.getElementById('station-count');
    var searchEl  = document.getElementById('search-keyword');
    var regionEl  = document.getElementById('filter-region');
    var btnSearch = document.getElementById('btn-search');
    var btnReset  = document.getElementById('btn-reset');
    if (!grid) return;

    var cards = Array.from(grid.querySelectorAll('.station-card'));

    // Use full card textContent so every visible word is searchable:
    // station name, address, city, services, hours, region badge — all of it.
    var cardTexts = cards.map(function (card) {
      return card.textContent.toLowerCase().replace(/\s+/g, ' ');
    });

    function runFilter() {
      var keyword = searchEl ? searchEl.value.toLowerCase().trim() : '';
      var region  = regionEl ? regionEl.value : '';
      var visible = 0;

      cards.forEach(function (card, i) {
        var okRegion  = !region  || card.dataset.region === region;
        var okKeyword = !keyword || cardTexts[i].indexOf(keyword) !== -1;
        var show = okRegion && okKeyword;
        // Use CSS class toggle — more reliable than the hidden property
        card.classList.toggle('is-hidden', !show);
        if (show) visible++;
      });

      if (countEl) countEl.textContent = visible;
      if (emptyEl) emptyEl.hidden = visible > 0;
    }

    // Set accurate initial count
    if (countEl) countEl.textContent = cards.length;

    // Debounce helper so rapid typing doesn't thrash the DOM
    var debounceTimer;
    function debouncedFilter() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(runFilter, 180);
    }

    if (btnSearch) btnSearch.addEventListener('click', runFilter);
    if (searchEl)  searchEl.addEventListener('input',   debouncedFilter);
    if (searchEl)  searchEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { clearTimeout(debounceTimer); runFilter(); }
    });
    if (regionEl) regionEl.addEventListener('change', runFilter);
    if (btnReset) {
      btnReset.addEventListener('click', function () {
        if (searchEl) searchEl.value = '';
        if (regionEl) regionEl.value = '';
        runFilter();
      });
    }
  }

  // ─── 8. PRODUCTS IN-PAGE NAV ─────────────────────────────────────────────────
  function initProductsNav() {
    var navLinks = document.querySelectorAll('.products-nav__link');
    if (!navLinks.length) return;

    var sections = Array.from(navLinks).map(function (link) {
      return document.querySelector(link.getAttribute('href'));
    }).filter(Boolean);

    var header = document.getElementById('site-header');

    function onScroll() {
      var headerH = header ? header.offsetHeight : 0;
      var offset  = headerH + 60;
      var scrollY = window.scrollY;
      var current = sections[0];

      sections.forEach(function (sec) {
        if (sec.getBoundingClientRect().top + scrollY - offset <= scrollY) {
          current = sec;
        }
      });

      navLinks.forEach(function (link) {
        link.classList.toggle('is-active', current && link.getAttribute('href') === '#' + current.id);
      });
    }

    window.addEventListener('scroll', rafThrottle(onScroll), { passive: true });
    onScroll();
  }

  // ─── 9. SCROLL REVEAL ────────────────────────────────────────────────────────
  function initScrollReveal() {
    if (!('IntersectionObserver' in window)) return;

    var selector = [
      '.card', '.fuel-card', '.value-card',
      '.station-card', '.service-item',
      '.about-snippet__grid', '.company-story__grid',
      '.timeline__item', '.mission-vision__block'
    ].join(', ');

    var elements = document.querySelectorAll(selector);
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.10 });

    elements.forEach(function (el) {
      el.classList.add('will-reveal');
      observer.observe(el);
    });
  }

  // ─── INIT ────────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    initStickyHeader();
    initMobileMenu();
    initActiveNav();
    initSmoothScroll();
    initFooterYear();
    initContactForm();
    initStationLocator();
    initProductsNav();
    initScrollReveal();
  });

}());
