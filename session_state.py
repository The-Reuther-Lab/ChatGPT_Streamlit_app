############################################################################################################
# Importing Libraries

import streamlit as st
import hmac
import pandas as pd
import random
import os
import time
import base64
import logging
import io
import config
import contextlib
import traceback
from openai import OpenAI

############################################################################################################
# Password protection

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
       # if hmac.compare_digest(st.session_state["password"], st.secrets["password"])
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False
 
            st.session_state["password_correct"]=True
    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False

if not check_password():
    st.stop()  # Do not continue if check_password is not True.

############################################################################################################
# Logging

logging.basicConfig(level=logging.DEBUG, filename='app_log.log', filemode='w',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

############################################################################################################
# Streamlit app layout

# Set the page to wide or centered mode
st.set_page_config(layout="centered")

# Streamlit app layout
st.title(config.app_title)
st.caption(config.app_author)
# st.markdown(config.intro_para)
with st.expander("INSTRUCTIONS:"):
    st.markdown(config.instructions)
st.sidebar.title(config.sidebar_title)
with st.sidebar:
        with st.expander("Click here for instructions."):
            st.write(config.sidebar_instructions)

############################################################################################################
# File Uploader in sidebar

# Load terms from a CSV file
# https://discuss.streamlit.io/t/how-to-upload-a-csv-file/7052/2
def load_terms(file_input):
    try:
        if isinstance(file_input, str):
            data = pd.read_csv(file_input)
        else:
            data = pd.read_csv(io.StringIO(file_input.read().decode('utf-8')))
        return data
    except Exception as e:
        st.error(f"An error occurred while loading the file: {str(e)}")
        logging.exception(f"Error loading file: {e}")

# Function to create a download link for a file
def create_download_link(file_path, file_name):
    try:
        with open(file_path, "rb") as file:
            file_content = file.read()
        encoded_content = base64.b64encode(file_content).decode("utf-8")
        download_link = f'<a href="data:file/csv;base64,{encoded_content}" download="{file_name}">Download {file_name}</a>'
        return download_link
    except FileNotFoundError:
        error_message = f"The file {file_name} was not found."
        st.error(error_message)
        logging.exception(error_message)
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        st.error(error_message)
        logging.exception(error_message)



# Download link for the template file
template_file_path = config.default_terms_csv

# File Uploader
uploaded_file = st.sidebar.file_uploader(" ", type=["csv"])
if uploaded_file is not None:
    logging.info(f"File uploaded: {uploaded_file.name}")
    st.session_state.uploaded_file = uploaded_file

# Load terms from the file
if 'uploaded_file' in st.session_state and st.session_state.uploaded_file is not None:
    terms = load_terms(st.session_state.uploaded_file)
else:
    terms = load_terms(template_file_path)

st.sidebar.markdown(create_download_link(template_file_path, "terms_template.csv"), unsafe_allow_html=True)

# line break in the sidebar
st.sidebar.markdown('<hr>', unsafe_allow_html=True)

############################################################################################################
# Term Selection and session state

# Function to select a random term and its schema
def select_random_term_and_schema(terms_df):
    if not terms_df.empty and 'TERM' in terms_df.columns and 'SCHEMA' in terms_df.columns:
        #random.seed(counter)
        selected_row = terms_df.sample()
        selected_term = selected_row['TERM'].values[0]
        selected_schema = selected_row['SCHEMA'].values[0]
        return selected_term, selected_schema
    else:
        return None, None
    
# Define a basic initial context at the beginning of your script
initial_context = {
    "role": "system",
    "content": config.initial_prompt
}

# Initialize the session state variables for selected term, schema, and display messages
if 'selected_term' not in st.session_state:
    st.session_state.selected_term = None
if 'selected_schema' not in st.session_state:
    st.session_state.selected_schema = None
if 'display_messages' not in st.session_state:
    st.session_state.display_messages = [initial_context]

# Initialize session states for the selected term, counter, and display flag
if 'selected_term' not in st.session_state:
    st.session_state.selected_term = None
if 'display_term' not in st.session_state:
   st.session_state.display_term = False

# Toggle term display and select a new term if needed
if st.button('Click to pick a term'):
    selected_term, selected_schema = select_random_term_and_schema(terms)
    st.session_state.selected_term = selected_term
    st.session_state.selected_schema = selected_schema
    st.session_state.display_term = True

    # Update the initial context with dynamic content
    updated_prompt = config.term_prompt(st.session_state.selected_term, st.session_state.selected_schema)
    initial_context = {
        "role": "system", 
        "content": updated_prompt}

    # Reset the conversation with the new initial context
    st.session_state.display_messages = [initial_context]

# Display the term if the condition is met
if st.session_state.display_term and st.session_state.selected_term:
    st.header(st.session_state.selected_term)
    # Pass the displayed term to the assistant as part of the message
    user_message = f"Define '{st.session_state.selected_term}':"
elif not st.session_state.selected_term:
    st.write("")

############################################################################################################
# ChatGPT
# Initialize the OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Initialize the session state variables if they don't exist
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = config.ai_model

if "display_messages" not in st.session_state:
    st.session_state.display_messages = [initial_context]

# Get user input
prompt = st.chat_input("Type your message here...")

# Input for new messages
if prompt:
    # Ensure the initial context is in the session state, add the user's message
    if not st.session_state["display_messages"]:
        st.session_state["display_messages"].append(initial_context)
    st.session_state["display_messages"].append({"role": "user", "content": prompt})

# Main chat container
with st.container(height=300, border=True):
    # Display chat history in reverse order including new messages
    for message in st.session_state["display_messages"][1:]:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(message["content"])

# Generate assistant's response and add it to the messages
    if prompt:
        # Call the OpenAI API without streaming to get a complete response
        response = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state["display_messages"]
            ],
            stream=False,  # Disable streaming
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        # Correctly extract the full response from the API's return object.
        full_response = response.choices[0].message.content

        # Append the full response to the session state for display.
        st.session_state["display_messages"].append({"role": "assistant", "content": full_response})

        # Directly display the assistant's response in the chat container
        with st.container():
            st.chat_message("assistant").write(full_response)

st.markdown(config.warning_message, unsafe_allow_html=True)

############################################################################################################

# Resources and About Sections in the Sidebar

st.sidebar.title("Resources")

for resource in config.resources:
    with st.sidebar:
        with st.expander(resource["title"]):
            st.markdown(f"Description: {resource['description']}")
            st.markdown(f"[Link]({resource['url']})")

# Footer
with st.sidebar:
    st.markdown("---")

    st.title("About")

   # Using the config objects in your Streamlit app
    st.markdown(config.app_creation_message, unsafe_allow_html=True)
    st.markdown(config.app_repo_license_message, unsafe_allow_html=True)

# Get user input
prompt = st.chat_input("Type your message here...")

############################################################################################################

#Code Interpreter

#python input
def safe_execute(code):
    """Executes the given code safely and returns the output or errors."""
    output = io.StringIO()
    try:
        # Redirect stdout to capture print statements
        with contextlib.redirect_stdout(output):
            exec(code, {"__builtins__": None}, {})  # Safe environment with no built-ins available
    except Exception as e:
        # Write the exception type and message to the output
        output.write(f'An error occurred: {str(e)}\n')
        # Also capture and write the traceback
        traceback.print_exc(file=output)
    
    return output.getvalue()

# Streamlit layout
st.subheader('Python Code Interpreter')
user_code = st.text_area("Enter your Python code here:", height=300, placeholder="Write your Python code here...")

if st.button('Run Code'):
    output = safe_execute(user_code)
    output_placeholder = st.empty()
    output_placeholder.code(output, language='python') 

############################################################################################################

#File Retrieval


#if  'user_input' not in st.session_state:
 #   st.session_state['user_input']=''

#st.title('SABER Conference App')

#st.write('Hello World! This is practice for the final streamlit app')

#user_input = st.text_input('Enter a custom message:', 'Hello streamlit')
#if user_input:
#    st.session_state['user_input']=user_input

#st.write(f"You entered: {st.session_state['user_input']}")

#st.write('Customized Message:',user_input)

#if  'user_input' not in st.session_state:
 #   st.session_state['user_input']=''

#st.title('SABER Conference App')

#st.write('Hello World! This is practice for the final streamlit app')

#user_input = st.text_input('Enter a custom message:', 'Hello streamlit')
#if user_input:
#    st.session_state['user_input']=user_input

#st.write(f"You entered: {st.session_state['user_input']}")

#st.write('Customized Message:',user_input)
