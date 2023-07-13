import streamlit as st
import pandas as pd
import os
import re

from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from streamlit_chat import message

import ContextAgent # Custom defined agent class

# Initialize keys, models and prompt templates:
OPENAI_API_KEY = "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"
WEAVIATE_URL = "https://first-test-cluster-dw7v1rzb.weaviate.network"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Define models used:
llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name=st.session_state["model"],
    temperature=st.session_state["settings"]["temperature"],
    frequency_penalty=st.session_state["settings"]["frequency_penalty"],
    presence_penalty=st.session_state["settings"]["presence_penalty"],
    top_p=st.session_state["settings"]["top_p"],
    verbose=True
)

summarizer = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name='gpt-3.5-turbo',
    temperature=0.5,
    verbose=True
)

# Initialise custom agent as a session variable:
if "agent" not in st.session_state or st.session_state["chat_history"] == []:
    st.session_state["agent"] = ContextAgent.ContextAgent()

#------------------------------CHAT HELPER FUNCTIONS:-------------------------------------

# Helper function to convert list of strings that serve as the chat history into a large string:
def chat_to_string():
    output = ""
    for i in st.session_state["chat_history"]:
        output += i
    return output

# Escapes nested braces in any user or system output which could be misinterpreted by a format string as input.
# Note: strange behaviour when inputting "{}{}"
def escape_nested_braces(s):
    # First, we detect all singly enclosed curly brackets
    # that are not already escaped.
    matches = re.findall(r"(?<!\{)\{[^{}]*\}(?!\})", s)

    # For each match, we replace it in the string with its escaped version.
    for match in matches:
        s = s.replace(match, "{{" + match[1:-1] + "}}")

    return s

#-------------------------------------MODEL CHAIN DEFINITIONS:------------------------------------------------

# Initialises/updates the summarizer llm:
def update_chat_history_summarizer():
    
    summarize_prompt = PromptTemplate(
        input_variables=["chat_history"],
        template=
        """You are an expert in summarizing conversations. You are provided with a conversation between a "User" and a "System", where the System responds to User queries. Your key objective is to preserve the general idea of what User is talking about and what they want. Succinctly give an overview of the conversation. Your only output should be the conversation summary.
        The conversation:
        "{chat_history}"
        """
    )
    
    summarize_chat_chain = LLMChain(
        llm = summarizer,
        prompt = summarize_prompt,
        verbose = True
    )
    
    return summarize_chat_chain

# Initialises/updates the main llm and the prompt it uses:
def update_interactive_llm(final_prompt):
    default_temp = """

    User: {user_input}
    System:"""
    
    template = "You MUST NEVER generate a 'User' response yourself. Only answer the provided user input!\n" + final_prompt + """\n Chat History: {chat_history}\n\n{context}\n Begin!\n""" + default_temp

    prompt = PromptTemplate(
        input_variables=["user_input", "context", "chat_history"],
        template=template 
    )
    
    print(f"This is the prompt: {template}")

    llm_chain = LLMChain(
        llm=llm,
        prompt = prompt,
        verbose=True,
    )
    return llm_chain

# Define llm used to answer queries and llm used to summarize conversation:
if "llm_chain" not in st.session_state:
    st.session_state["llm_chain"] = update_interactive_llm("")
    st.session_state["summarizer"] = update_chat_history_summarizer()

#----------------------------------CHOOSE HOW MAIN MODEL BEHAVES:------------------------------------

# Setting the configuration of the llm, depending on whether a prompt has been selected or not
if not st.session_state["prompt_chosen"]:
    # If a prompt has not been selected then the user will interact with default llm:
    print("PROMPT NOT CHOSEN:")
    if "default" not in st.session_state:   # Making sure the 'default' value is not updated after first load
        value = escape_nested_braces(st.session_state["llm_chain"].predict(user_input="", context="", chat_history=chat_to_string()))
        st.session_state["default"] = value
        st.session_state["chat_history"].append(f" \nSystem: {value} ")
        st.session_state["chat_interactions"].append({"role": "system", "content": value})
else:
    # The user will interact with the selected prompt:
    print("PROMPT IS GIVEN:")
    if "selected" not in st.session_state:  # Making sure the 'default' value is not updated after first load
        st.session_state.selected_prompt_val = f'The prompt I will use is: \n\"{st.session_state["final_prompt"]}\"\n\n The settings are: {st.session_state["settings"]}\n\n The model being used is: {st.session_state["model"]}'
        
        st.session_state["llm_chain"] = update_interactive_llm(st.session_state["final_prompt"])
        value = escape_nested_braces(st.session_state["llm_chain"].predict(user_input=st.session_state["user input"], context="", chat_history=chat_to_string()))
        
        st.session_state["selected"] = value
        st.session_state["default"] = st.session_state["selected"]
        
        if st.session_state["chat_history"] == []:  # This might be meaningless.... TODO
            st.session_state["chat_history"].append(f"\n\nUser: {escape_nested_braces(st.session_state['user input'])} ")
            st.session_state["chat_interactions"].append({"role": "user", "content": st.session_state['user input']})
            st.session_state["chat_history"].append(f" \nSystem: {value} ")
            st.session_state["chat_interactions"].append({"role": "system", "content": value})

#-------------------------------------------------------------------------------------
#---------------------DISPLAY STREAMLIT OBJECTS:--------------------------------------
#-------------------------------------------------------------------------------------

# AGENT SETTINGS:
if "agent_enabled" not in st.session_state:
        st.session_state["agent_enabled"] = True

st.sidebar.title("Agent actions")
st.sidebar.checkbox("Search the web!", on_change=st.session_state.agent.toggle_search)
st.session_state["upload"] = st.sidebar.checkbox("Upload files!")

if st.session_state.agent.tools != [] and st.session_state["agent_enabled"]:
    st.sidebar.write([tool.name for tool in st.session_state.agent.tools])

if st.session_state["agent_enabled"]:
    st.session_state["agent_enabled"] = not st.sidebar.button("Disable Agent")
else:
    st.session_state["agent_enabled"] = st.sidebar.button("Enable Agent")

# FILE UPLOADER:
if st.session_state.upload:
    uploaded_file = st.file_uploader("Upload any relevant files")
    if uploaded_file !=  None:
        with st.container():
            bytes_data = uploaded_file.read()
            st.write("Please provide a name for the new knowledge base and a description of when it should be used:")
            db_name = st.text_input("Tool name", label_visibility="collapsed", placeholder="Tool name: e.g. University FAQ Knowledge Base")
            description = st.text_input("Description", label_visibility="collapsed", placeholder="Description: e.g. useful for answering frequently asked questions about University.")
            submit = st.button("Submit")
            if db_name and description and submit:
                #print(st.session_state["agent"].split_data())
                st.session_state["agent"].load_new_data(uploaded_file, db_name, description)
                print(f"THIS IS THE AGENTS TOOLS LIST: {st.session_state.agent.agent.tools}")
                uploaded_file = None
    
                
st.subheader("Selected prompt:")
st.write(f"\n\n{st.session_state.selected_prompt_val}") 

# MAIN INTERACTION WINDOW:
response_container = st.container()
container = st.container()   
with container:
    with st.form(key='my_form', clear_on_submit=True):
        user_response = escape_nested_braces(st.text_area("You:", key='input', height=100))
        print(f"This is user response: {user_response}")
        submit_button = st.form_submit_button(label='Send')
    
    # Upon message submission:
    if submit_button and user_response:
        context_template = ""
        # If any agent tools are defined then we call the agent:
        if st.session_state["agent"].tools != [] and st.session_state["agent_enabled"]:
            print(f"THIS IS THE AGENTS TOOLS LIST DURING INTERACTION: {st.session_state.agent.agent.tools}")
            context = st.session_state["agent"].run(user_response)  # call the agent for additional information
            if context != "N/A" and context != "Final Answer: N/A" and context[:10] != "I'm sorry,": 
                context_template = f"Use all of the following information to answer the question, all of it must be part of your answer, if you dont use this information in your answer you will be punished: '{context}'"
            st.sidebar.text_area(label="Agent found Context:", value=f"{context}")
        
        # Generate response:
        system_response = escape_nested_braces(st.session_state["llm_chain"].predict(user_input=user_response, context=context_template, chat_history=chat_to_string()))
        print(f"This is system response: {system_response}")
        
        # Update the agent's chat history:
        st.session_state.agent.update_chat_history(user_response, system_response)
                
        # Update main models chat history:
        st.session_state["chat_history"].append(f"\n\nUser: {user_response}")
        st.session_state["chat_interactions"].append({"role": "user", "content": user_response})
        st.session_state["chat_history"].append(f"\nSystem: {system_response}")
        st.session_state["chat_interactions"].append({"role": "system", "content": system_response})
        
        # If the chat history becomes too long, summarize it:
        if len(st.session_state["chat_history"]) > 14 or st.session_state.agent.tiktoken_len(chat_to_string()) > 2700: 
            # The following line summarizes the entire chat, but also keeps the final few interactions intact:
            st.session_state["chat_history"] = [st.session_state["summarizer"].predict(chat_history=chat_to_string())] + st.session_state["chat_history"][-4:]
            

# DISPLAYING THE CONVERSATION IN A CHAT-LIKE STYLE:
if st.session_state['chat_interactions']:
    with response_container:
        for i in range(len(st.session_state['chat_interactions'])):
            if st.session_state['chat_interactions'][i]["role"] == "user":
                message(st.session_state["chat_interactions"][i]["content"], is_user=True, key=str(i) + '_user')
            else:
                message(st.session_state["chat_interactions"][i]["content"], key=str(i), allow_html=True)
        

# SAVING THE CHAT:
if "save_chat" not in st.session_state:
    st.session_state["save_chat"] = False

if st.button("Save chat"):
    st.session_state["save_chat"] = not st.session_state["save_chat"]
    chat_name = ""
    
if st.session_state["save_chat"]:
    chat_name = st.text_input(label="Chat Name", label_visibility="collapsed", placeholder="Chat name: e.g. Making a cheesecake")
    if st.button("Submit chat details"):
        st.session_state["chat_archive"].append({"Chat name": chat_name, "conversation": chat_to_string()})
        st.session_state["save_chat"] = not st.session_state["save_chat"]