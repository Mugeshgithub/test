gsap.registerPlugin(ScrollTrigger);

/* ── helpers ── */
const qs  = (s, ctx = document) => ctx.querySelector(s);
const qsa = (s, ctx = document) => [...ctx.querySelectorAll(s)];

/* ═══════════════════════════════════════════════════════════════
   NAV — fade in on load
═══════════════════════════════════════════════════════════════ */
gsap.to('#nav', {
  opacity: 1,
  y: 0,
  duration: 0.8,
  ease: 'power2.out',
  delay: 0.3,
});

/* ═══════════════════════════════════════════════════════════════
   SECTION 1 — HERO
═══════════════════════════════════════════════════════════════ */
const heroTL = gsap.timeline({ delay: 0.5 });

heroTL
  .to('.hero__tag', { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' })
  .to('.hero__title .word', {
    opacity: 1,
    y: 0,
    duration: 0.6,
    stagger: 0.12,
    ease: 'back.out(1.5)',
  }, '-=0.2')
  .to('.hero__sub', { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' }, '-=0.2')
  .to('.hero__actions', { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' }, '-=0.2')
  .to('.hero__visual', { opacity: 1, x: 0, duration: 0.7, ease: 'power2.out' }, '-=0.5')
  .to('.scroll-hint', { opacity: 1, duration: 0.5, ease: 'power2.out' }, '-=0.2');

/* floating stethoscope */
gsap.to('.stethoscope-icon', {
  y: -12,
  duration: 2.5,
  ease: 'sine.inOut',
  yoyo: true,
  repeat: -1,
  delay: 1.5,
});

/* background circles slow drift */
gsap.to('.circle--1', { x: 20, y: -20, duration: 8, yoyo: true, repeat: -1, ease: 'sine.inOut' });
gsap.to('.circle--2', { x: -15, y: 15, duration: 10, yoyo: true, repeat: -1, ease: 'sine.inOut' });
gsap.to('.circle--3', { x: 10, y: 10,  duration: 7,  yoyo: true, repeat: -1, ease: 'sine.inOut' });

/* ═══════════════════════════════════════════════════════════════
   SECTION 2 — ABOUT
═══════════════════════════════════════════════════════════════ */
ScrollTrigger.create({
  trigger: '#about',
  start: 'top 80%',
  once: true,
  onEnter() {
    const tl = gsap.timeline();

    tl.to('.doctor-card__img-wrap', {
        opacity: 1,
        x: 0,
        duration: 0.8,
        ease: 'power3.out',
      })
      .to('.doctor-card__badge', {
        opacity: 1,
        scale: 1,
        duration: 0.5,
        ease: 'back.out(2)',
      }, '-=0.3')
      .to('.about__right', {
        opacity: 1,
        x: 0,
        duration: 0.8,
        ease: 'power3.out',
      }, '-=0.6')
      .to('.credential', {
        opacity: 1,
        x: 0,
        duration: 0.5,
        stagger: 0.15,
        ease: 'power2.out',
      }, '-=0.4');
  },
});

/* ═══════════════════════════════════════════════════════════════
   SECTION 3 — SERVICES
═══════════════════════════════════════════════════════════════ */
ScrollTrigger.create({
  trigger: '#services',
  start: 'top 80%',
  once: true,
  onEnter() {
    const tl = gsap.timeline();

    tl.to('.services__header', {
        opacity: 1,
        y: 0,
        duration: 0.6,
        ease: 'power2.out',
      })
      .to('.service-card', {
        opacity: 1,
        scale: 1,
        y: 0,
        duration: 0.55,
        stagger: {
          each: 0.1,
          from: 'start',
        },
        ease: 'back.out(1.3)',
      }, '-=0.2');
  },
});

/* hover tilt on service cards */
qsa('.service-card').forEach(card => {
  card.addEventListener('mousemove', e => {
    const r = card.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width  - 0.5;
    const y = (e.clientY - r.top)  / r.height - 0.5;
    gsap.to(card, { rotationY: x * 10, rotationX: -y * 10, transformPerspective: 600, duration: 0.3, ease: 'power2.out' });
  });
  card.addEventListener('mouseleave', () => {
    gsap.to(card, { rotationY: 0, rotationX: 0, duration: 0.5, ease: 'elastic.out(1,0.5)' });
  });
});

/* ═══════════════════════════════════════════════════════════════
   SECTION 4 — TESTIMONIALS
═══════════════════════════════════════════════════════════════ */
ScrollTrigger.create({
  trigger: '#testimonials',
  start: 'top 80%',
  once: true,
  onEnter() {
    const tl = gsap.timeline();

    tl.to('#testimonials .section__tag', { opacity: 1, duration: 0.4, ease: 'power2.out' })
      .to('#testimonials .section__title', { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' }, '-=0.1')
      .to('.testimonial-card', {
        opacity: 1,
        y: 0,
        duration: 0.6,
        stagger: 0.1,
        ease: 'power2.out',
      }, '-=0.2')
      .to('.stats-row', { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out' }, '-=0.2');

    /* counter animation */
    qsa('.stat__num').forEach(el => {
      const target = parseInt(el.dataset.target, 10);
      gsap.to({ val: 0 }, {
        val: target,
        duration: 2,
        ease: 'power2.out',
        delay: 0.4,
        onUpdate() {
          el.textContent = Math.round(this.targets()[0].val).toLocaleString();
        },
      });
    });
  },
});

/* testimonial slider */
let currentSlide = 0;
const track = qs('#testimonialTrack');
const dots   = qsa('.dot');
const cards  = qsa('.testimonial-card');

function goToSlide(idx) {
  currentSlide = idx;
  gsap.to(track, {
    x: -(idx * (track.parentElement.offsetWidth + 0)),
    duration: 0.55,
    ease: 'power2.inOut',
  });
  dots.forEach((d, i) => d.classList.toggle('dot--active', i === idx));
}

dots.forEach((dot, i) => dot.addEventListener('click', () => goToSlide(i)));

/* auto-advance every 4 s */
const autoSlide = setInterval(() => {
  goToSlide((currentSlide + 1) % cards.length);
}, 4000);

/* pause on hover */
track.parentElement.addEventListener('mouseenter', () => clearInterval(autoSlide));

/* ═══════════════════════════════════════════════════════════════
   SECTION 5 — CONTACT
═══════════════════════════════════════════════════════════════ */
ScrollTrigger.create({
  trigger: '#contact',
  start: 'top 80%',
  once: true,
  onEnter() {
    const tl = gsap.timeline();

    tl.to('.contact__left', {
        opacity: 1,
        x: 0,
        duration: 0.8,
        ease: 'power3.out',
      })
      .to('.contact__right', {
        opacity: 1,
        x: 0,
        duration: 0.8,
        ease: 'power3.out',
      }, '-=0.5');
  },
});

/* form submit animation */
qs('#contactForm').addEventListener('submit', e => {
  e.preventDefault();
  const btn  = qs('#submitBtn');
  const text = qs('.btn__text', btn);
  const ring = qs('.btn__pulse', btn);

  gsap.timeline()
    .to(ring, { scale: 2, opacity: 0.6, duration: 0.2 })
    .to(ring, { scale: 3, opacity: 0,   duration: 0.3 })
    .to(btn,  { scale: 0.96, duration: 0.1 }, '<')
    .to(btn,  { scale: 1,    duration: 0.2 });

  text.textContent = '✓ Appointment Requested!';
  btn.style.background = '#2ECC71';
  setTimeout(() => {
    text.textContent = 'Confirm Appointment';
    btn.style.background = '';
  }, 3000);
});

/* ═══════════════════════════════════════════════════════════════
   NAV ACTIVE LINK on scroll
═══════════════════════════════════════════════════════════════ */
const sections = qsa('.section');
const navLinks = qsa('.nav__links a');

sections.forEach(sec => {
  ScrollTrigger.create({
    trigger: sec,
    start: 'top 50%',
    end: 'bottom 50%',
    onEnter()      { setActive(sec.id); },
    onEnterBack()  { setActive(sec.id); },
  });
});

function setActive(id) {
  navLinks.forEach(a => {
    a.style.color = a.getAttribute('href') === `#${id}`
      ? 'var(--teal)'
      : '';
  });
}

/* ═══════════════════════════════════════════════════════════════
   SNAP — ensure ScrollTrigger works with CSS snap
═══════════════════════════════════════════════════════════════ */
ScrollTrigger.config({ ignoreMobileResize: true });
ScrollTrigger.refresh();
