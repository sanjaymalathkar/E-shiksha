// Contact form handler with Excel storage
document.addEventListener('DOMContentLoaded', function() {
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

                // First, save to Firebase (original functionality)
                try {
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
                } catch (firebaseError) {
                    console.warn('Firebase storage failed, continuing with Excel storage:', firebaseError);
                }

                // Second, save to Excel via our API endpoint
                const response = await fetch('/api/contact/submit', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        name: name,
                        email: email,
                        exam: exam,
                        message: message
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.detail || 'Failed to save contact information');
                }

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
});
