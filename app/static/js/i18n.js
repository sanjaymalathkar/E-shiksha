/**
 * Internationalization (i18n) module for E-Shiksha
 * Handles client-side translation of UI elements
 */

// Default language
let currentLanguage = 'en';

// Load translations
const loadTranslations = async () => {
    try {
        const response = await fetch(`/static/translations/${currentLanguage}.json`);
        if (!response.ok) {
            throw new Error(`Failed to load translations: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error loading translations:', error);
        // Fallback to embedded translations if available
        return window.fallbackTranslations?.[currentLanguage] || {};
    }
};

// Initialize translations
let translations = {};

// Translate the entire page
const translatePage = async () => {
    // Get saved language or default to English
    currentLanguage = localStorage.getItem('language') || 'en';

    // Update HTML lang attribute
    document.documentElement.lang = currentLanguage;

    // Load translations for current language
    translations = await loadTranslations();

    // Translate all elements with data-i18n attribute
    translateElements();

    // Translate all elements with data-i18n-placeholder attribute (for input placeholders)
    translatePlaceholders();

    // Translate all elements with data-i18n-title attribute (for tooltips)
    translateTitles();

    // Translate all elements with data-i18n-aria-label attribute (for accessibility)
    translateAriaLabels();

    // Dispatch event that translations are complete
    document.dispatchEvent(new CustomEvent('translationsLoaded'));
};

// Translate elements with data-i18n attribute
const translateElements = () => {
    const elements = document.querySelectorAll('[data-i18n]');

    elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        const translation = getNestedTranslation(key);

        if (translation) {
            element.textContent = translation;
        }
    });
};

// Translate input placeholders
const translatePlaceholders = () => {
    const elements = document.querySelectorAll('[data-i18n-placeholder]');

    elements.forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        const translation = getNestedTranslation(key);

        if (translation) {
            element.setAttribute('placeholder', translation);
        }
    });
};

// Translate element titles (tooltips)
const translateTitles = () => {
    const elements = document.querySelectorAll('[data-i18n-title]');

    elements.forEach(element => {
        const key = element.getAttribute('data-i18n-title');
        const translation = getNestedTranslation(key);

        if (translation) {
            element.setAttribute('title', translation);
        }
    });
};

// Translate ARIA labels for accessibility
const translateAriaLabels = () => {
    const elements = document.querySelectorAll('[data-i18n-aria-label]');

    elements.forEach(element => {
        const key = element.getAttribute('data-i18n-aria-label');
        const translation = getNestedTranslation(key);

        if (translation) {
            element.setAttribute('aria-label', translation);
        }
    });
};

// Get nested translation using dot notation (e.g., "common.buttons.submit")
const getNestedTranslation = (key) => {
    if (!key) return null;

    const keys = key.split('.');
    let result = translations;

    for (const k of keys) {
        if (result && typeof result === 'object' && k in result) {
            result = result[k];
        } else {
            return null;
        }
    }

    return result;
};

// Change language and translate page
const changeLanguage = async (language) => {
    if (language) {
        localStorage.setItem('language', language);
        currentLanguage = language;
        await translatePage();
    }
};

// Initialize translations when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Set initial language from localStorage or browser preference
    const savedLanguage = localStorage.getItem('language');
    const browserLanguage = navigator.language.split('-')[0];
    const supportedLanguages = ['en', 'hi', 'kn'];

    currentLanguage = savedLanguage ||
                     (supportedLanguages.includes(browserLanguage) ? browserLanguage : 'en');

    // Update language selector if it exists
    const languageSelector = document.getElementById('language-selector');
    if (languageSelector) {
        languageSelector.value = currentLanguage;
    }

    // Initial translation
    translatePage();
});

// Export functions for use in other scripts
window.i18n = {
    translate: getNestedTranslation,
    changeLanguage,
    getCurrentLanguage: () => currentLanguage
};
