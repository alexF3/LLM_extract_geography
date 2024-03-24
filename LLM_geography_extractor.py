
## Demo of using Lllama and Mistral 7b to extract geographic info from affiliations
## Prep: Download Ollama (Linux or Mac...Windows in preview): https://ollama.com/
## Have Ollama running in the background !ollama pull mistral:instruct if you need to download the Mistral 7b model (~4 GB)

## import libraries (!pip install ______ if you need to install a library in your venv)
from langchain.llms import Ollama
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import pandas as pd
import time
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

start = time.time() # hack the clock for total run time

## load author affiliations (drawn from a .nbib citation manager file from a PubMed search for JAMA articles 2013-2013) https://pubmed.ncbi.nlm.nih.gov/
## ping me if you'd like the code that generated this .csv
df = pd.read_csv('data/jama_editorials_dataframe.csv')

aff_list = df.firstAffiliation.value_counts().reset_index()['index'].tolist()
aff_list = aff_list[:25]
eval_frame = pd.DataFrame({'firstAffiliation':aff_list})
# For now, filter out affiliations with parenthesis that are likely to be bulk affiliations with many authors to parse
eval_frame = eval_frame[ ~eval_frame.firstAffiliation.str.contains("\(")]

################################################
# get Nation of affiliation
#
# !ollama pull mistral:instruct

llm = Ollama(model='mistral:instruct',
            callback_manager = CallbackManager([StreamingStdOutCallbackHandler()]),
            temperature=0.0, # minimize "creativity" in model responses
            top_p=0.3,num_predict=10)# keep the responses short)

prompt = PromptTemplate(
    input_variables=["affiliation"],
    template="""Read the affiliation and return only the nation that the affiliation is in.
Examples:
1. user: "columbia university, new york, NY"
response: usa
2. user: "peter munk cardiac centre at university health network, toronto, ontario, canada."
response: canada
3. user: "editor of a journal"
response: unknown

Return only nation or unkown
affiliation: " {affiliation}""",
    stopwords=["\n"],
    max_tokens=10
)

from langchain.chains import LLMChain
chain = LLMChain(llm=llm, prompt=prompt)

def getNation(affiliation):
    """get the nation an author's affiliation is in (return "unknown" if unable)

    Args:
        affiliation (str): author affiliation

    Returns:
        nation (str): the nation an affiliation is in ("usa", <another nation>, or "unkown")
    """    
    response = chain.run(affiliation)
    return response
eval_frame['mistral_INSTRUCT_response'] = eval_frame.firstAffiliation.apply(getNation)
# Clean up the results a bit:
eval_frame.mistral_INSTRUCT_response = eval_frame.mistral_INSTRUCT_response.str.lower()
eval_frame.mistral_INSTRUCT_response = eval_frame.mistral_INSTRUCT_response.str.replace('united states','usa')
eval_frame['mistral_INSTRUCT_response'] = eval_frame['mistral_INSTRUCT_response'].str.replace('response: ','')
eval_frame.mistral_INSTRUCT_response = eval_frame.mistral_INSTRUCT_response.str.rstrip().str.lstrip()

##############################################

# Get City, State of affiliation
llm = Ollama(model='mistral:instruct',
            callback_manager = CallbackManager([StreamingStdOutCallbackHandler()]),
            temperature=0.0, # minimize "creativity" in model responses
            top_p=0.3,num_predict=10) # keep the responses short)

prompt = PromptTemplate(
    input_variables=["affiliation"],
    template="""Read the affiliation and return only the city and state that the affiliation is in.
Examples:
1. user: "columbia university, new york, NY"
new york, ny
2. user: "department of psychiatry, university of california, san francisco."
response: san francisco, ca
3. user: "a colony on mars"
response: unknown

Return only city, state or unkown
affiliation: " {affiliation}""",
    stopwords=["\n"],
    max_tokens=10
)

from langchain.chains import LLMChain
chain = LLMChain(llm=llm, prompt=prompt)


def getCityState(affiliation,nation):
    """reterieve the city, state of an affiliation if it was determined to be in the United States

    Args:
        affiliation (str): first listed author affiliation
        nation (str): nation extracted from first listed author affiliation by previous Mistral call

    Returns:
        city_state (str): <city>, <state> or "unknown"
    """    
    if 'usa' in nation:
        return(chain.run(affiliation).replace('Response: ', '').replace('response: ', '').split('\n')[0])
    return ''

# Apply the function row-wise over the dataframe  
eval_frame['city_state'] = eval_frame.apply(lambda row: getCityState(row['firstAffiliation'], row['mistral_INSTRUCT_response']), axis=1)


eval_frame.rename(columns={'mistral_INSTRUCT_response':'nation'},inplace=True)


eval_frame.to_csv('JAMA_all_Mistral7b_24k.csv', index=False)

import decimal

def dollarFormat(amount):
  dollar = "${:.2f}".format(amount)
  return dollar


# Let's try to estimtae what this run would have cost to run on AWS Bedrock with Lllama2 or Mistral 7b
# https://aws.amazon.com/bedrock/pricing/

eval_frame = pd.read_csv('JAMA_all_Mistral7b_24k.csv')


def check_prices(eval_frame):
    print('Rough estimate of AWS Bedrock prices for this run:')
    eval_frame['input_word_count'] = eval_frame['firstAffiliation'].str.split().str.len()
    eval_frame['nation_output_word_count'] = eval_frame['nation'].str.split().str.len()
    eval_frame['city_state_output_word_count'] = eval_frame['city_state'].str.split().str.len()
    # Llama2 price
    llama2_13b_input_price = 0.00075/1000
    llama2_13b_output_price = 0.00100/1000
    nation_cost = eval_frame.input_word_count.sum() *1.3 * llama2_13b_input_price + eval_frame.nation_output_word_count.sum() * 1.3 * llama2_13b_output_price
    city_state_cost = eval_frame.input_word_count.sum() *1.3 * llama2_13b_input_price + eval_frame.city_state_output_word_count.sum() * 1.3 * llama2_13b_output_price
    print('Llama2 13b costs:')
    print('nation cost: ', dollarFormat(nation_cost))
    print('city state cost: ', dollarFormat(city_state_cost))
    print('')

    mistral_7b_input_price = 0.00015/1000
    mistral_7b_output_price = 0.0002/1000
    nation_cost = eval_frame.input_word_count.sum() *1.3 * mistral_7b_input_price + eval_frame.nation_output_word_count.sum() * 1.3 * mistral_7b_output_price
    city_state_cost = eval_frame.input_word_count.sum() *1.3 * mistral_7b_input_price + eval_frame.city_state_output_word_count.sum() * 1.3 * mistral_7b_output_price
    print('Mistral 7b costs:')
    print('nation cost: ', dollarFormat(nation_cost))
    print('city state cost: ', dollarFormat(city_state_cost))    
    
    
check_prices(eval_frame)

total_time = time.time() - start

print('total affiliations processed: {}'.format(len(eval_frame)))
print('total time: {}'.format(total_time))  

####
## Create an eval file of randomly sampled entries for error stats:

# Get number of rows in dataframe
num_rows = len(full_frame) 

# Calculate number of rows to sample
sample_size = 2000

# Use sample() to get a random sample of rows  
eval_sample = eval_frame.sample(n=sample_size).to_csv('jama_Mistral7b_2k_eval_sample.csv', index=False)


