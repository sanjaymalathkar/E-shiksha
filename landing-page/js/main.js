// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize loader
    initLoader();

    // Initialize navigation
    initNavigation();

    // Initialize animations
    initAnimations();

    // Initialize theme toggle
    initThemeToggle();

    // Initialize Lottie animations
    initLottieAnimations();

    // Initialize contact form
    initContactForm();

    // Initialize smooth scroll
    initSmoothScroll();
});

// Initialize loader
function initLoader() {
    const loaderContainer = document.querySelector('.loader-container');

    // Hide loader after page is loaded
    window.addEventListener('load', function() {
        setTimeout(function() {
            loaderContainer.classList.add('hidden');
        }, 500);
    });
}

// Initialize navigation
function initNavigation() {
    const menuToggle = document.querySelector('.menu-toggle');
    const navMenu = document.querySelector('.nav-menu');
    const navLinks = document.querySelectorAll('.nav-link');
    const navbar = document.querySelector('.navbar');

    // Toggle mobile menu
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            navMenu.classList.toggle('active');
            document.body.classList.toggle('no-scroll');
        });
    }

    // Close mobile menu when clicking on a link
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            navMenu.classList.remove('active');
            document.body.classList.remove('no-scroll');
        });
    });

    // Add active class to nav links based on scroll position
    window.addEventListener('scroll', function() {
        const scrollPosition = window.scrollY;

        // Show/hide navbar on scroll
        if (scrollPosition > 100) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }

        // Show navbar when scrolling up
        if (scrollPosition < lastScrollPosition) {
            navbar.classList.add('visible');
        } else {
            navbar.classList.remove('visible');
        }

        lastScrollPosition = scrollPosition;

        // Update active nav link
        const sections = document.querySelectorAll('section');

        sections.forEach(section => {
            const sectionTop = section.offsetTop - 100;
            const sectionHeight = section.offsetHeight;
            const sectionId = section.getAttribute('id');

            if (scrollPosition >= sectionTop && scrollPosition < sectionTop + sectionHeight) {
                navLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === `#${sectionId}`) {
                        link.classList.add('active');
                    }
                });
            }
        });
    });

    // Initialize last scroll position
    let lastScrollPosition = 0;
}

// Initialize animations
function initAnimations() {
    // Initialize GSAP
    if (typeof gsap !== 'undefined') {
        // Hero section animations
        gsap.from('.hero-title', {
            opacity: 0,
            y: 50,
            duration: 1,
            ease: 'power3.out'
        });

        gsap.from('.hero-description', {
            opacity: 0,
            y: 30,
            duration: 1,
            delay: 0.3,
            ease: 'power3.out'
        });

        gsap.from('.hero-buttons', {
            opacity: 0,
            y: 30,
            duration: 1,
            delay: 0.6,
            ease: 'power3.out'
        });

        // Feature cards animations
        if (typeof ScrollTrigger !== 'undefined') {
            gsap.registerPlugin(ScrollTrigger);

            gsap.from('.feature-card', {
                scrollTrigger: {
                    trigger: '.features-container',
                    start: 'top 80%'
                },
                opacity: 0,
                y: 50,
                stagger: 0.2,
                duration: 0.8,
                ease: 'power3.out'
            });

            gsap.from('.about-content', {
                scrollTrigger: {
                    trigger: '.about-container',
                    start: 'top 80%'
                },
                opacity: 0,
                x: -50,
                duration: 1,
                ease: 'power3.out'
            });

            gsap.from('.contact-info, .contact-form', {
                scrollTrigger: {
                    trigger: '.contact-container',
                    start: 'top 80%'
                },
                opacity: 0,
                y: 50,
                stagger: 0.3,
                duration: 1,
                ease: 'power3.out'
            });
        }
    }
}

// Initialize theme toggle
function initThemeToggle() {
    const themeToggle = document.querySelector('.theme-toggle');
    const themeIcon = document.querySelector('.theme-toggle i');

    // Check for saved theme preference or use device preference
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.body.classList.add('dark-mode');
        themeIcon.classList.remove('fa-moon');
        themeIcon.classList.add('fa-sun');
    }

    // Toggle theme on click
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            document.body.classList.toggle('dark-mode');

            if (document.body.classList.contains('dark-mode')) {
                localStorage.setItem('theme', 'dark');
                themeIcon.classList.remove('fa-moon');
                themeIcon.classList.add('fa-sun');
            } else {
                localStorage.setItem('theme', 'light');
                themeIcon.classList.remove('fa-sun');
                themeIcon.classList.add('fa-moon');
            }
        });
    }
}

// Initialize Lottie animations
function initLottieAnimations() {
    if (typeof lottie !== 'undefined') {
        // Hero animation - Education/Learning
        const heroLottieElement = document.getElementById('hero-lottie');
        if (heroLottieElement) {
            lottie.loadAnimation({
                container: heroLottieElement,
                renderer: 'svg',
                loop: true,
                autoplay: true,
                path: 'https://assets9.lottiefiles.com/packages/lf20_bhebjzpu.json' // Education/Learning animation
            });
        }

        // About animation - AI/Machine Learning
        const aboutLottieElement = document.getElementById('about-lottie');
        if (aboutLottieElement) {
            lottie.loadAnimation({
                container: aboutLottieElement,
                renderer: 'svg',
                loop: true,
                autoplay: true,
                path: 'https://assets5.lottiefiles.com/packages/lf20_KU3FGB.json' // AI/Machine Learning animation
            });
        }

        // Add floating animation to exam topics
        const examTopics = document.querySelectorAll('.exam-topics span');
        if (examTopics.length > 0) {
            examTopics.forEach((topic, index) => {
                gsap.to(topic, {
                    y: -5,
                    duration: 1.5,
                    repeat: -1,
                    yoyo: true,
                    ease: 'power1.inOut',
                    delay: index * 0.1
                });
            });
        }

        // Add 3D tilt effect to exam cards
        const examCards = document.querySelectorAll('.exam-card');
        if (examCards.length > 0) {
            examCards.forEach(card => {
                card.addEventListener('mousemove', function(e) {
                    const rect = this.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;

                    const xPercent = x / rect.width;
                    const yPercent = y / rect.height;

                    const maxRotate = 10; // Maximum rotation in degrees
                    const rotateX = (0.5 - yPercent) * maxRotate;
                    const rotateY = (xPercent - 0.5) * maxRotate;

                    this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;
                });

                card.addEventListener('mouseleave', function() {
                    this.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateZ(0)';
                });
            });
        }
    }
}

// Initialize contact form
function initContactForm() {
    const contactForm = document.getElementById('contactForm');

    if (contactForm) {
        contactForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Get form data
            const name = document.getElementById('name').value;
            const email = document.getElementById('email').value;
            const exam = document.getElementById('exam').value;
            const message = document.getElementById('message').value;

            try {
                // Show loading
                Swal.fire({
                    title: 'Sending message...',
                    text: 'Please wait',
                    allowOutsideClick: false,
                    showConfirmButton: false,
                    willOpen: () => {
                        Swal.showLoading();
                    }
                });

                // Import Firebase modules
                const { getFirestore, collection, addDoc } = await import("https://www.gstatic.com/firebasejs/11.6.1/firebase-firestore.js");
                const { initializeApp } = await import("https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js");

                // Firebase configuration
                const firebaseConfig = {
                    apiKey: "AIzaSyBqsz_mDEHarA-_HzSZNfO9y3LMbf8HSio",
                    authDomain: "education-58a96.firebaseapp.com",
                    projectId: "education-58a96",
                    storageBucket: "education-58a96.firebasestorage.app",
                    messagingSenderId: "86814013646",
                    appId: "1:86814013646:web:1613b7043c29b2f7b9389f",
                    measurementId: "G-K2Z953CCYG"
                };

                // Initialize Firebase
                const app = initializeApp(firebaseConfig);
                const db = getFirestore(app);

                // Add contact form data to Firestore
                await addDoc(collection(db, "contacts"), {
                    name: name,
                    email: email,
                    exam: exam,
                    message: message,
                    createdAt: new Date().toISOString()
                });

                // Success message
                Swal.fire({
                    icon: 'success',
                    title: 'Message Sent!',
                    text: 'We will get back to you soon with information about ' + exam + ' preparation.',
                    confirmButtonColor: '#4F46E5'
                });

                // Reset form
                contactForm.reset();

            } catch (error) {
                console.error('Error sending message:', error);

                Swal.fire({
                    icon: 'error',
                    title: 'Message Failed',
                    text: 'Failed to send message. Please try again.',
                    confirmButtonColor: '#4F46E5'
                });
            }
        });
    }
}

// Initialize smooth scroll
function initSmoothScroll() {
    const scrollLinks = document.querySelectorAll('a[href^="#"]');

    scrollLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Only prevent default if the href is not just "#"
            if (this.getAttribute('href') !== '#') {
                e.preventDefault();

                const targetId = this.getAttribute('href');
                const targetElement = document.querySelector(targetId);

                if (targetElement) {
                    const navbarHeight = document.querySelector('.navbar').offsetHeight;
                    const targetPosition = targetElement.offsetTop - navbarHeight;

                    window.scrollTo({
                        top: targetPosition,
                        behavior: 'smooth'
                    });
                }
            }
        });
    });
}
