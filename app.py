import streamlit as st

def main():
    # Page config
    st.set_page_config(page_title="Text Input Demo", page_icon="📝", layout="centered")

    # Title and description
    st.title("📝 Text Input Demo with Streamlit")
    st.write(
        "Type or paste any text below. "
        "I'll show it back to you along with some basic stats."
    )

    # Text input area
    user_text = st.text_area(
        "Enter your text here:",
        height=200,
        placeholder="Start typing something... (a note, a paragraph, anything!)",
    )

    # Button to process text
    if st.button("Process Text"):
        if not user_text.strip():
            st.warning("Please enter some text before processing.")
        else:
            # Simple stats
            num_chars = len(user_text)
            num_chars_no_spaces = len(user_text.replace(" ", ""))
            words = user_text.split()
            num_words = len(words)
            num_lines = user_text.count("\n") + 1

            st.subheader("🔍 Text Statistics")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Characters", num_chars)
            with col2:
                st.metric("Chars (no spaces)", num_chars_no_spaces)
            with col3:
                st.metric("Words", num_words)

main()