import re

def convert_latex_to_plain(text):
    # Remove math delimiters ($$ or $)
    text = text.replace('$$', '')
    text = text.replace('$', '')
    
    # Replace specific LaTeX commands with plain text equivalents
    # Replace \sqrt{s} with a square-root notation (√s)
    text = text.replace(r'\sqrt{s}', '√s')
    
    # Convert \text{} parts into just the text inside the braces.
    # This regex finds occurrences of \text{...} and replaces them with the inner content.
    text = re.sub(r'\\text\s*\{([^}]*)\}', r'\1', text)
    
    # Remove any \hspace commands (which may include negative spaces or similar)
    text = re.sub(r'\\hspace\{[^}]*\}', '', text)
    
    # Clean up any extra whitespace resulting from the removals
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

# Example usage:
example = (
    """
Search for Higgs boson decays into a pair of pseudoscalar particles in the γγτhadτhad final state using pp collisions at $$ \sqrt{\textrm{s}} $$ = 13 TeV with the ATLAS detector
"""
)

converted_text = convert_latex_to_plain(example)
print(converted_text)