// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize loader
    initLoader();
    
    // Initialize sidebar
    initSidebar();
    
    // Initialize animations
    initAnimations();
    
    // Initialize theme toggle
    initThemeToggle();
    
    // Initialize notifications
    initNotifications();
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

// Initialize sidebar
function initSidebar() {
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const sidebarLinks = document.querySelectorAll('.sidebar-menu a');
    
    // Toggle sidebar on mobile
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            mainContent.classList.toggle('expanded');
        });
    }
    
    // Add active class to sidebar links
    sidebarLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Prevent default only if it's a hash link
            if (this.getAttribute('href').startsWith('#')) {
                e.preventDefault();
                
                // Remove active class from all links
                sidebarLinks.forEach(link => {
                    link.parentElement.classList.remove('active');
                });
                
                // Add active class to clicked link
                this.parentElement.classList.add('active');
                
                // On mobile, close sidebar after clicking a link
                if (window.innerWidth < 992) {
                    sidebar.classList.add('collapsed');
                    mainContent.classList.remove('expanded');
                }
            }
        });
    });
}

// Initialize animations
function initAnimations() {
    // Initialize GSAP
    if (typeof gsap !== 'undefined') {
        // Welcome section animations
        gsap.from('.welcome-section', {
            opacity: 0,
            y: 30,
            duration: 0.8,
            ease: 'power3.out'
        });
        
        // Stats cards animations
        gsap.from('.stat-card', {
            opacity: 0,
            y: 30,
            stagger: 0.1,
            duration: 0.6,
            delay: 0.3,
            ease: 'power3.out'
        });
        
        // Recent activity animations
        gsap.from('.section-header', {
            opacity: 0,
            y: 20,
            duration: 0.6,
            delay: 0.6,
            ease: 'power3.out'
        });
        
        gsap.from('.activity-item', {
            opacity: 0,
            x: -30,
            stagger: 0.1,
            duration: 0.6,
            delay: 0.8,
            ease: 'power3.out'
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

// Initialize notifications
function initNotifications() {
    const notificationsIcon = document.querySelector('.notifications');
    
    if (notificationsIcon) {
        notificationsIcon.addEventListener('click', function() {
            Swal.fire({
                title: 'Notifications',
                html: `
                    <div class="notifications-container">
                        <div class="notification-item">
                            <div class="notification-icon">
                                <i class="fas fa-user-plus"></i>
                            </div>
                            <div class="notification-content">
                                <h4>New Follower</h4>
                                <p>Jane Smith started following you</p>
                                <span class="notification-time">2 hours ago</span>
                            </div>
                        </div>
                        <div class="notification-item">
                            <div class="notification-icon">
                                <i class="fas fa-comment"></i>
                            </div>
                            <div class="notification-content">
                                <h4>New Message</h4>
                                <p>You received a message from John Doe</p>
                                <span class="notification-time">5 hours ago</span>
                            </div>
                        </div>
                        <div class="notification-item">
                            <div class="notification-icon">
                                <i class="fas fa-heart"></i>
                            </div>
                            <div class="notification-content">
                                <h4>Project Liked</h4>
                                <p>Someone liked your "Portfolio Website" project</p>
                                <span class="notification-time">Yesterday</span>
                            </div>
                        </div>
                    </div>
                `,
                showConfirmButton: false,
                showCloseButton: true,
                customClass: {
                    container: 'notifications-popup-container',
                    popup: 'notifications-popup',
                    content: 'notifications-popup-content'
                }
            });
        });
    }
}

// Add 3D hover effect to stat cards
function init3DHoverEffect() {
    const statCards = document.querySelectorAll('.stat-card');
    
    statCards.forEach(card => {
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

// Call 3D hover effect initialization
init3DHoverEffect();
