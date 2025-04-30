// Auth Modal Module for E-Shiksha Landing Page

// DOM Elements
const loginBtn = document.querySelector('.login-btn');
const signupBtn = document.querySelector('.signup-btn');
const loginModal = document.getElementById('login-modal');
const signupModal = document.getElementById('signup-modal');
const closeButtons = document.querySelectorAll('.close-modal');
const showSignupLink = document.getElementById('show-signup');
const showLoginLink = document.getElementById('show-login');
const loginForm = document.getElementById('login-form');
const signupForm = document.getElementById('signup-form');
const googleLoginBtn = document.getElementById('google-login');
const googleSignupBtn = document.getElementById('google-signup');

// Firebase Auth
let auth;
let firebaseApp;

// Initialize Firebase Auth
async function initializeFirebaseAuth() {
    try {
        // Import Firebase modules
        const { initializeApp } = await import("https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js");
        const { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword, signInWithPopup, GoogleAuthProvider, updateProfile } = 
            await import("https://www.gstatic.com/firebasejs/11.6.1/firebase-auth.js");

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
        firebaseApp = initializeApp(firebaseConfig);
        auth = getAuth(firebaseApp);
        
        // Set up Google provider
        const googleProvider = new GoogleAuthProvider();
        
        // Email/Password Login
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            
            try {
                showLoadingState(loginForm);
                const userCredential = await signInWithEmailAndPassword(auth, email, password);
                const user = userCredential.user;
                
                // Show success message
                Swal.fire({
                    icon: 'success',
                    title: 'Login Successful',
                    text: `Welcome back, ${user.displayName || user.email}!`,
                    timer: 2000,
                    showConfirmButton: false
                });
                
                // Close modal
                closeModal(loginModal);
                
                // Reset form
                loginForm.reset();
                
                // Update UI for logged in user
                updateUIForLoggedInUser(user);
                
            } catch (error) {
                console.error("Login error:", error);
                
                // Show error message
                Swal.fire({
                    icon: 'error',
                    title: 'Login Failed',
                    text: getErrorMessage(error),
                });
            } finally {
                hideLoadingState(loginForm);
            }
        });
        
        // Email/Password Signup
        signupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const name = document.getElementById('signup-name').value;
            const email = document.getElementById('signup-email').value;
            const password = document.getElementById('signup-password').value;
            const confirmPassword = document.getElementById('signup-confirm-password').value;
            
            // Validate passwords match
            if (password !== confirmPassword) {
                Swal.fire({
                    icon: 'error',
                    title: 'Passwords Do Not Match',
                    text: 'Please make sure your passwords match.'
                });
                return;
            }
            
            try {
                showLoadingState(signupForm);
                const userCredential = await createUserWithEmailAndPassword(auth, email, password);
                const user = userCredential.user;
                
                // Update profile with name
                await updateProfile(user, {
                    displayName: name
                });
                
                // Show success message
                Swal.fire({
                    icon: 'success',
                    title: 'Account Created',
                    text: `Welcome to E-Shiksha, ${name}!`,
                    timer: 2000,
                    showConfirmButton: false
                });
                
                // Close modal
                closeModal(signupModal);
                
                // Reset form
                signupForm.reset();
                
                // Update UI for logged in user
                updateUIForLoggedInUser(user);
                
            } catch (error) {
                console.error("Signup error:", error);
                
                // Show error message
                Swal.fire({
                    icon: 'error',
                    title: 'Signup Failed',
                    text: getErrorMessage(error),
                });
            } finally {
                hideLoadingState(signupForm);
            }
        });
        
        // Google Login
        googleLoginBtn.addEventListener('click', async () => {
            try {
                showLoadingState(googleLoginBtn);
                const result = await signInWithPopup(auth, googleProvider);
                const user = result.user;
                
                // Show success message
                Swal.fire({
                    icon: 'success',
                    title: 'Login Successful',
                    text: `Welcome back, ${user.displayName || user.email}!`,
                    timer: 2000,
                    showConfirmButton: false
                });
                
                // Close modal
                closeModal(loginModal);
                
                // Update UI for logged in user
                updateUIForLoggedInUser(user);
                
            } catch (error) {
                console.error("Google login error:", error);
                
                // Show error message
                Swal.fire({
                    icon: 'error',
                    title: 'Google Login Failed',
                    text: getErrorMessage(error),
                });
            } finally {
                hideLoadingState(googleLoginBtn);
            }
        });
        
        // Google Signup
        googleSignupBtn.addEventListener('click', async () => {
            try {
                showLoadingState(googleSignupBtn);
                const result = await signInWithPopup(auth, googleProvider);
                const user = result.user;
                
                // Show success message
                Swal.fire({
                    icon: 'success',
                    title: 'Account Created',
                    text: `Welcome to E-Shiksha, ${user.displayName || user.email}!`,
                    timer: 2000,
                    showConfirmButton: false
                });
                
                // Close modal
                closeModal(signupModal);
                
                // Update UI for logged in user
                updateUIForLoggedInUser(user);
                
            } catch (error) {
                console.error("Google signup error:", error);
                
                // Show error message
                Swal.fire({
                    icon: 'error',
                    title: 'Google Signup Failed',
                    text: getErrorMessage(error),
                });
            } finally {
                hideLoadingState(googleSignupBtn);
            }
        });
        
    } catch (error) {
        console.error("Error initializing Firebase Auth:", error);
    }
}

// Helper function to get user-friendly error messages
function getErrorMessage(error) {
    switch (error.code) {
        case 'auth/invalid-email':
            return 'Invalid email address format.';
        case 'auth/user-disabled':
            return 'This account has been disabled.';
        case 'auth/user-not-found':
            return 'No account found with this email.';
        case 'auth/wrong-password':
            return 'Incorrect password.';
        case 'auth/email-already-in-use':
            return 'This email is already in use.';
        case 'auth/weak-password':
            return 'Password is too weak. Use at least 6 characters.';
        case 'auth/popup-closed-by-user':
            return 'Login popup was closed before completing the sign in.';
        case 'auth/cancelled-popup-request':
            return 'The login popup was cancelled.';
        case 'auth/popup-blocked':
            return 'Login popup was blocked by the browser.';
        default:
            return error.message || 'An error occurred. Please try again.';
    }
}

// Helper function to show loading state
function showLoadingState(element) {
    if (element.tagName === 'FORM') {
        const button = element.querySelector('button[type="submit"]');
        if (button) {
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
            button.disabled = true;
        }
    } else {
        element.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
        element.disabled = true;
    }
}

// Helper function to hide loading state
function hideLoadingState(element) {
    if (element.tagName === 'FORM') {
        const button = element.querySelector('button[type="submit"]');
        if (button) {
            button.innerHTML = button.getAttribute('data-original-text') || 'Submit';
            button.disabled = false;
        }
    } else {
        element.innerHTML = element.getAttribute('data-original-text') || 'Submit';
        element.disabled = false;
    }
}

// Update UI for logged in user
function updateUIForLoggedInUser(user) {
    // Update login/signup buttons
    loginBtn.textContent = 'My Account';
    loginBtn.href = '#';
    signupBtn.textContent = 'Logout';
    signupBtn.href = '#';
    
    // Add logout functionality
    signupBtn.addEventListener('click', (e) => {
        e.preventDefault();
        auth.signOut().then(() => {
            // Reset UI
            loginBtn.textContent = 'Login';
            signupBtn.textContent = 'Sign Up';
            
            // Show logout message
            Swal.fire({
                icon: 'success',
                title: 'Logged Out',
                text: 'You have been successfully logged out.',
                timer: 2000,
                showConfirmButton: false
            });
        });
    });
}

// Modal Functions
function openModal(modal) {
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden'; // Prevent scrolling
}

function closeModal(modal) {
    modal.style.display = 'none';
    document.body.style.overflow = ''; // Restore scrolling
}

// Close modal when clicking outside
window.addEventListener('click', (e) => {
    if (e.target === loginModal) {
        closeModal(loginModal);
    }
    if (e.target === signupModal) {
        closeModal(signupModal);
    }
});

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Save original button text
    const buttons = document.querySelectorAll('button');
    buttons.forEach(button => {
        button.setAttribute('data-original-text', button.innerHTML);
    });
    
    // Initialize Firebase Auth
    initializeFirebaseAuth();
    
    // Open login modal
    loginBtn.addEventListener('click', (e) => {
        e.preventDefault();
        openModal(loginModal);
    });
    
    // Open signup modal
    signupBtn.addEventListener('click', (e) => {
        e.preventDefault();
        openModal(signupModal);
    });
    
    // Close modals
    closeButtons.forEach(button => {
        button.addEventListener('click', () => {
            closeModal(loginModal);
            closeModal(signupModal);
        });
    });
    
    // Switch between login and signup
    showSignupLink.addEventListener('click', (e) => {
        e.preventDefault();
        closeModal(loginModal);
        openModal(signupModal);
    });
    
    showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        closeModal(signupModal);
        openModal(loginModal);
    });
});
