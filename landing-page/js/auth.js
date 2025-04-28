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
}

// Initialize animations
function initAnimations() {
    // Initialize GSAP
    if (typeof gsap !== 'undefined') {
        // Form animations
        gsap.from('.auth-form-header', {
            opacity: 0,
            y: -30,
            duration: 0.8,
            ease: 'power3.out'
        });
        
        gsap.from('.auth-form .form-group', {
            opacity: 0,
            y: 20,
            stagger: 0.1,
            duration: 0.6,
            delay: 0.3,
            ease: 'power3.out'
        });
        
        gsap.from('.auth-btn', {
            opacity: 0,
            y: 20,
            duration: 0.6,
            delay: 0.8,
            ease: 'power3.out'
        });
        
        gsap.from('.auth-divider, .social-auth, .auth-redirect', {
            opacity: 0,
            y: 20,
            stagger: 0.1,
            duration: 0.6,
            delay: 1,
            ease: 'power3.out'
        });
        
        // Add hover effect to form inputs
        const formGroups = document.querySelectorAll('.form-group');
        
        formGroups.forEach(group => {
            const input = group.querySelector('input, textarea');
            
            if (input) {
                input.addEventListener('focus', function() {
                    gsap.to(this, {
                        duration: 0.3,
                        y: -2,
                        ease: 'power2.out'
                    });
                });
                
                input.addEventListener('blur', function() {
                    if (!this.value) {
                        gsap.to(this, {
                            duration: 0.3,
                            y: 0,
                            ease: 'power2.out'
                        });
                    }
                });
            }
        });
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
        // Login animation
        const loginLottieElement = document.getElementById('login-lottie');
        if (loginLottieElement) {
            lottie.loadAnimation({
                container: loginLottieElement,
                renderer: 'svg',
                loop: true,
                autoplay: true,
                path: 'https://assets9.lottiefiles.com/packages/lf20_hy4txm7l.json' // Secure login animation
            });
        }
        
        // Signup animation
        const signupLottieElement = document.getElementById('signup-lottie');
        if (signupLottieElement) {
            lottie.loadAnimation({
                container: signupLottieElement,
                renderer: 'svg',
                loop: true,
                autoplay: true,
                path: 'https://assets10.lottiefiles.com/packages/lf20_q5pk6p1k.json' // User registration animation
            });
        }
        
        // Forgot password animation
        const forgotPasswordLottieElement = document.getElementById('forgot-password-lottie');
        if (forgotPasswordLottieElement) {
            lottie.loadAnimation({
                container: forgotPasswordLottieElement,
                renderer: 'svg',
                loop: true,
                autoplay: true,
                path: 'https://assets2.lottiefiles.com/private_files/lf30_GjHLSt.json' // Reset password animation
            });
        }
    }
}

// Add 3D tilt effect to auth form
function init3DTiltEffect() {
    const authForm = document.querySelector('.auth-form-container');
    
    if (authForm) {
        authForm.addEventListener('mousemove', function(e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const xPercent = x / rect.width;
            const yPercent = y / rect.height;
            
            const maxRotate = 5; // Maximum rotation in degrees
            const rotateX = (0.5 - yPercent) * maxRotate;
            const rotateY = (xPercent - 0.5) * maxRotate;
            
            this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
        });
        
        authForm.addEventListener('mouseleave', function() {
            this.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
        });
    }
}

// Call 3D tilt effect initialization
init3DTiltEffect();
