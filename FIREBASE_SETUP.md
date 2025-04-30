# Firebase Authentication Setup

This document provides instructions for setting up Firebase Authentication for the E-Shiksha 2 application.

## Prerequisites

1. A Google account
2. A Firebase project (create one at [Firebase Console](https://console.firebase.google.com/))

## Setup Steps

### 1. Create a Firebase Project

1. Go to the [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project"
3. Enter a project name (e.g., "E-Shiksha")
4. Follow the setup wizard to create your project

### 2. Enable Authentication Methods

1. In your Firebase project, go to "Authentication" in the left sidebar
2. Click on "Sign-in method"
3. Enable the following authentication methods:
   - Email/Password
   - Google
   - (Optional) Any other methods you want to support

### 3. Create a Web App

1. In your Firebase project, click on the gear icon next to "Project Overview" and select "Project settings"
2. Scroll down to "Your apps" section
3. Click on the web icon (</>) to add a web app
4. Register your app with a nickname (e.g., "E-Shiksha Web")
5. Copy the Firebase configuration object (it looks like this):

```javascript
const firebaseConfig = {
  apiKey: "your-api-key",
  authDomain: "your-project-id.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project-id.appspot.com",
  messagingSenderId: "your-messaging-sender-id",
  appId: "your-app-id",
  measurementId: "your-measurement-id"
};
```

### 4. Generate a Firebase Admin SDK Service Account Key

1. In your Firebase project settings, go to the "Service accounts" tab
2. Click "Generate new private key" button
3. Save the JSON file securely

### 5. Configure Environment Variables

Add the following environment variables to your `.env` file:

```
# Firebase Web SDK Configuration
FIREBASE_CONFIG={"apiKey":"your-api-key","authDomain":"your-project-id.firebaseapp.com","projectId":"your-project-id","storageBucket":"your-project-id.appspot.com","messagingSenderId":"your-messaging-sender-id","appId":"your-app-id","measurementId":"your-measurement-id"}

# Firebase Admin SDK Configuration
FIREBASE_CREDENTIALS_PATH=/path/to/your/firebase-credentials.json
```

Alternatively, you can set individual Firebase configuration variables:

```
FIREBASE_API_KEY=your-api-key
FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
FIREBASE_MESSAGING_SENDER_ID=your-messaging-sender-id
FIREBASE_APP_ID=your-app-id
FIREBASE_MEASUREMENT_ID=your-measurement-id
```

And for the Firebase Admin SDK, you can also provide the credentials directly:

```
FIREBASE_CREDENTIALS={"type":"service_account","project_id":"your-project-id","private_key_id":"your-private-key-id","private_key":"your-private-key","client_email":"your-client-email","client_id":"your-client-id","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"your-client-cert-url"}
```

### 6. MongoDB Setup

Make sure MongoDB is running and accessible. Set the following environment variables:

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=e_shiksha
```

If you're using MongoDB Atlas or another hosted MongoDB service, use the appropriate connection string.

## Testing the Setup

1. Start the application
2. Navigate to the login page
3. Try signing in with Google
4. Check the MongoDB database to verify that user data is being stored correctly

## Troubleshooting

### Common Issues

1. **Firebase initialization fails**: Check that your Firebase configuration is correct
2. **Authentication fails**: Ensure that the authentication methods are enabled in Firebase
3. **MongoDB connection fails**: Verify that MongoDB is running and accessible
4. **Firebase Admin SDK initialization fails**: Check that your service account key is valid and accessible

### Logs

Check the application logs for error messages related to Firebase or MongoDB.

## Security Considerations

1. Never commit your Firebase credentials to version control
2. Use environment variables or secure secret management for all sensitive configuration
3. Set up proper Firebase Security Rules to protect your data
4. Implement proper user role management in your application
