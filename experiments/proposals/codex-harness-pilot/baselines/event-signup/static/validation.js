const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Mirrors the server rules in app/registrations.py so most mistakes are caught
// before a request is sent. The server remains the source of truth.
export function validateSignup(values) {
  const errors = {};
  if (!values.name.trim()) errors.name = "Please enter your name.";
  else if (values.name.trim().length > 100) errors.name = "Name must be at most 100 characters.";
  if (!EMAIL_PATTERN.test(values.email.trim())) errors.email = "Please enter a valid email address.";
  if (values.affiliation.trim().length > 100) errors.affiliation = "Affiliation must be at most 100 characters.";
  if (values.note.trim().length > 500) errors.note = "Notes must be at most 500 characters.";
  return errors;
}
