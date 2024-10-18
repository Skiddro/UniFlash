import gettext
import locale
import os

__version__ = "0.1"

# Construct translation directory path using os.path.join for cross-platform compatibility
locale_path = os.path.join(os.path.dirname(__file__), "locale")

# Use gettext for translations, with dynamic locale selection and path handling
translation = gettext.translation(
    "uniflash", 
    locale_path, 
    [locale.getlocale()[0]], 
    fallback=True
)

# Install the translation globally
translation.install()
i18n = translation.gettext
