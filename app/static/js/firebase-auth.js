// Firebase Authentication Integration

// Firebase configuration
const firebaseConfig = {
  // Your Firebase configuration will be provided by the environment
  // This will be populated at runtime from the server
};

// Initialize Firebase
let firebaseInitialized = false;
let auth = null;

// Initialize Firebase when the configuration is available
function initializeFirebase(config) {
  if (firebaseInitialized) return;
  
  try {
    firebase.initializeApp(config);
    auth = firebase.auth();
    firebaseInitialized = true;
    console.log("Firebase initialized successfully");
  } catch (error) {
    console.error("Error initializing Firebase:", error);
  }
}

// Get Firebase configuration from the server
async function getFirebaseConfig() {
  try {
    const response = await fetch('/api/firebase-auth/config');
    if (!response.ok) {
      throw new Error(`Failed to get Firebase config: ${response.statusText}`);
    }
    const config = await response.json();
    initializeFirebase(config);
  } catch (error) {
    console.error("Error getting Firebase config:", error);
  }
}

// Sign in with email and password
async function signInWithEmailPassword(email, password) {
  if (!firebaseInitialized) {
    console.error("Firebase not initialized");
    return null;
  }
  
  try {
    const userCredential = await auth.signInWithEmailAndPassword(email, password);
    const user = userCredential.user;
    const idToken = await user.getIdToken();
    return { user, idToken };
  } catch (error) {
    console.error("Error signing in with email and password:", error);
    throw error;
  }
}

// Sign in with Google
async function signInWithGoogle() {
  if (!firebaseInitialized) {
    console.error("Firebase not initialized");
    return null;
  }
  
  try {
    const provider = new firebase.auth.GoogleAuthProvider();
    const userCredential = await auth.signInWithPopup(provider);
    const user = userCredential.user;
    const idToken = await user.getIdToken();
    return { user, idToken };
  } catch (error) {
    console.error("Error signing in with Google:", error);
    throw error;
  }
}

// Sign up with email and password
async function signUpWithEmailPassword(email, password, displayName) {
  if (!firebaseInitialized) {
    console.error("Firebase not initialized");
    return null;
  }
  
  try {
    const userCredential = await auth.createUserWithEmailAndPassword(email, password);
    const user = userCredential.user;
    
    // Update user profile with display name
    if (displayName) {
      await user.updateProfile({ displayName });
    }
    
    const idToken = await user.getIdToken();
    return { user, idToken };
  } catch (error) {
    console.error("Error signing up with email and password:", error);
    throw error;
  }
}

// Send password reset email
async function sendPasswordResetEmail(email) {
  if (!firebaseInitialized) {
    console.error("Firebase not initialized");
    return false;
  }
  
  try {
    await auth.sendPasswordResetEmail(email);
    return true;
  } catch (error) {
    console.error("Error sending password reset email:", error);
    throw error;
  }
}

// Sign out
async function signOut() {
  if (!firebaseInitialized) {
    console.error("Firebase not initialized");
    return false;
  }
  
  try {
    await auth.signOut();
    return true;
  } catch (error) {
    console.error("Error signing out:", error);
    throw error;
  }
}

// Get current user
function getCurrentUser() {
  if (!firebaseInitialized) {
    console.error("Firebase not initialized");
    return null;
  }
  
  return auth.currentUser;
}

// Register with the server after Firebase authentication
async function registerWithServer(idToken, username = null) {
  try {
    const response = await fetch('/api/firebase-auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        id_token: idToken,
        username: username
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to register with server');
    }
    
    return await response.json();
  } catch (error) {
    console.error("Error registering with server:", error);
    throw error;
  }
}

// Initialize Firebase when the page loads
document.addEventListener('DOMContentLoaded', getFirebaseConfig);
