// Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyDhikLQrEQXTBtZU4-T-Bg7yCwIZ4vKo_I",
    authDomain: "e-shiksha-2.firebaseapp.com",
    projectId: "e-shiksha-2",
    storageBucket: "e-shiksha-2.appspot.com",
    messagingSenderId: "1002536188546",
    appId: "1:1002536188546:web:d5c2d7b9f7c9c3c9c3c9c3"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// Get client IP address
async function getClientIP() {
    try {
        const response = await fetch('https://api.ipify.org?format=json');
        const data = await response.json();
        return data.ip;
    } catch (error) {
        console.error('Error getting client IP:', error);
        return '';
    }
}

// Show error message
function showError(message) {
    const errorElement = document.getElementById('error-message');
    errorElement.textContent = message;
    errorElement.classList.remove('hidden');
    setTimeout(() => {
        errorElement.classList.add('hidden');
    }, 5000);
}

// Show success message
function showSuccess(message) {
    const successElement = document.getElementById('success-message');
    successElement.textContent = message;
    successElement.classList.remove('hidden');
    setTimeout(() => {
        successElement.classList.add('hidden');
    }, 5000);
}

// Create user in MongoDB
async function createUserInMongoDB(userData) {
    try {
        const response = await fetch('/api/direct-user/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to create user in MongoDB');
        }

        return await response.json();
    } catch (error) {
        console.error('Error creating user in MongoDB:', error);
        throw error;
    }
}

// Handle email/password signup
async function handleEmailSignup(event) {
    event.preventDefault();
    
    // Get form values
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const phone = document.getElementById('phone').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    // Validate form
    if (!name || !email || !phone || !password || !confirmPassword) {
        showError('Please fill in all fields');
        return;
    }
    
    if (password !== confirmPassword) {
        showError('Passwords do not match');
        return;
    }
    
    try {
        // Show loading state
        document.getElementById('signup-button').disabled = true;
        document.getElementById('signup-button').textContent = 'Creating Account...';
        
        // Step 1: Create user in Firebase
        const userCredential = await firebase.auth().createUserWithEmailAndPassword(email, password);
        const user = userCredential.user;
        
        // Update display name in Firebase
        await user.updateProfile({
            displayName: name
        });
        
        console.log('User created in Firebase:', user.uid);
        
        // Step 2: Create user in MongoDB
        const clientIP = await getClientIP();
        const mongoDBUser = await createUserInMongoDB({
            firebase_uid: user.uid,
            email: email,
            password: password, // Will be hashed on the server
            username: name,
            display_name: name,
            mobile_number: phone,
            role: "student",
            client_ip: clientIP
        });
        
        console.log('User created in MongoDB:', mongoDBUser);
        
        // Show success message
        showSuccess('Account created successfully! Redirecting to login...');
        
        // Redirect to login page after 2 seconds
        setTimeout(() => {
            window.location.href = '/pages/login.html';
        }, 2000);
        
    } catch (error) {
        console.error('Error during signup:', error);
        showError(error.message || 'Failed to create account');
        
        // Reset button state
        document.getElementById('signup-button').disabled = false;
        document.getElementById('signup-button').textContent = 'Sign Up';
    }
}

// Handle Google signup
async function handleGoogleSignup() {
    try {
        // Show loading state
        document.getElementById('google-signup-button').disabled = true;
        
        // Sign in with Google
        const provider = new firebase.auth.GoogleAuthProvider();
        const userCredential = await firebase.auth().signInWithPopup(provider);
        const user = userCredential.user;
        
        console.log('User signed in with Google:', user.uid);
        
        // Create user in MongoDB
        const randomPassword = Math.random().toString(36).slice(-10);
        const clientIP = await getClientIP();
        
        const mongoDBUser = await createUserInMongoDB({
            firebase_uid: user.uid,
            email: user.email,
            password: randomPassword, // Will be hashed on the server
            username: user.displayName || user.email.split('@')[0],
            display_name: user.displayName || user.email.split('@')[0],
            mobile_number: user.phoneNumber || '',
            role: "student",
            client_ip: clientIP
        });
        
        console.log('User created in MongoDB:', mongoDBUser);
        
        // Show success message
        showSuccess('Account created successfully! Redirecting to dashboard...');
        
        // Redirect to dashboard after 2 seconds
        setTimeout(() => {
            window.location.href = '/app';
        }, 2000);
        
    } catch (error) {
        console.error('Error during Google signup:', error);
        showError(error.message || 'Failed to sign up with Google');
        
        // Reset button state
        document.getElementById('google-signup-button').disabled = false;
    }
}

// Initialize event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Email/password signup form
    const signupForm = document.getElementById('signup-form');
    if (signupForm) {
        signupForm.addEventListener('submit', handleEmailSignup);
    }
    
    // Google signup button
    const googleSignupButton = document.getElementById('google-signup-button');
    if (googleSignupButton) {
        googleSignupButton.addEventListener('click', handleGoogleSignup);
    }
});
