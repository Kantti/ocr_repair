# -*- coding: utf-8 -*-
import json
import re
import operator
import dbm

INPUT = 0
OUTPUT = 1

START = 0
MIDDLE = 1
END = 2



def parse_data_row(line):
    
    line = re.split("\t", line)[1:]
    l = int(len(line)/2)
    return  [line[i*2:i*2+2] for i in range(0, l)]

def parse_corrections_to_list(corrections):

    correction_list = []

    for row in corrections:

        for pair in row:

            correction_list.append(pair)

    return correction_list

def character_combinations(count, word):

    return [[word[0:i], word[i:i+count], word[i+count:len(word)]] for i in range(0, len(word)-count+1)]
    
def get_trigram_factor(fragment, table):

#calculates the probability of a given fragments last three characters in the table of trigrams
    
    if len(fragment) == 1: fragment = "##"+fragment
    elif len(fragment) == 2: fragment = "#"+fragment
    else: fragment = fragment[-3:]
    
    if fragment in table: return table[fragment]
    else: return table["nonce"]
   
def get_character_frequency_table(word_list):

#combines a character frequency list from list of corrected words
#{c1 : n1, c2 : n2}

   
    frequency_list = dict()

    for word in word_list:

        combinations = []

        for i in range(1, 3):

            combinations.extend(character_combinations(i, word))

        for c in combinations:

            character = c[MIDDLE]
            
            if character in frequency_list: frequency_list[character] += 1
            else: frequency_list.update( { character : 1 } )

    return frequency_list


def build_replacement_probability_table(correction_list, character_frequency_list):

#return a dict of dicts, where keys are characters and values are key-value pairs of characters possible replacements and their respective probabilities

    table = { x : { x : character_frequency_list[x] } for x in character_frequency_list }
    
    for pair in correction_list:
        if pair[INPUT] in table:
            table[pair[INPUT]][pair[INPUT]] -= 1
            if pair[OUTPUT] in table[pair[INPUT]]: table[pair[INPUT]][pair[OUTPUT]] += 1
            else: table[pair[INPUT]].update( { pair[OUTPUT] : 1 })
        else:
            table.update( { pair[INPUT] : { pair[INPUT] : 0, pair[OUTPUT] : 1 } } )
            
    for row in table:
        row_sum = sum(table[row].values())
        for col in table[row]: 
            table[row][col] = table[row][col] / row_sum
            
    for row in table:
        if len(row) > 1:
            for col in table[row]:
                factor=1
                for r in row:
                    factor = factor*table[r][r]
                table[row][col] = table[row][col]*(1-factor)

    unknown_c = "abcdefghijklmnopqrstuvxyzäö"

    unknown = { c : 1/(len(unknown_c)+1) for c in unknown_c }

    table.update( { "unknown" : unknown })
    table["unknown"].update( { "unknown" : 1/len(unknown)+1 } )

    return table
        

def add_split_marks(fragment, count):

    for i in range(1, count): fragment += "<+>"

    return fragment
                     
def get_split_list(correction_list):

    return [x for x in correction_list if len(x[INPUT]) > 1]

        
def get_word_combinations(word):

    combinations = []
    for i in range(1,4):
        combinations.extend(character_combinations(i, word))

    return combinations

def check_split_list(split_list, fragment):
    return [x[INPUT] for x in split_list if fragment.startswith(x[INPUT])]


def run_through_matrix(word, correction_matrix, table):
    guesses = dict()
    fragments = dict()
    for i in range(0, len(correction_matrix)):
        new_fragments = []

        for j in correction_matrix[i]:
            j_sub = j
            j_prob = correction_matrix[i][j]
            if len(fragments) > 0:
                for f in fragments:
                    if f["fragment"].endswith("<+>"):
                        
                        new_fragments.append( { "fragment" : re.sub("<\+>", "", f["fragment"], count=1), "prob" : f["prob"] } )

                    else:
                        
                        k = f["fragment"]
                   
                        nf = k+j_sub
                        
                        trigram_factor = get_trigram_factor(nf, table)
                        prob = f["prob"]*j_prob*trigram_factor
                        new_fragments.append( { "fragment" : nf ,  "prob" : prob}  )
                        

            else:
                trigram_factor = get_trigram_factor(j_sub, table)
                new_fragments.append( { "fragment" : j_sub,  "prob" : j_prob*trigram_factor }  )

        new_fragments = get_top_100_fragments(new_fragments)
        fragments = new_fragments

   

    return fragments

    corpus_sizes = { "182x" : {"tokens" : 575179,  "types"  : 65941 },
                     "183x" : {"tokens" : 1377160, "types"  : 128880 },
                     "184x" : {"tokens"  : 2998726, "types" : 197429 },
                     "185x" : {"tokens"  : 17038824,"types" : 525143 },
                     "186x" : {"tokens"  : 37430663, "types": 916087 },  
                     "187x" : {"tokens"  : 79244434, "types": 1413128 }, 
                     "188x" : {"tokens"  : 276140381, "types": 2824262 }, 
                     "189x" : {"tokens"  : 732014562, "types": 4849579 }}

def ensure_dbs():
    for corpus in corpus_sizes:
        try:
            dbm.open("resources/grams/OF_klk_fi_1grams_"+corpus+"-20140905.db")
        except dbm.error:
            with dbm.open("resources/grams/OF_klk_fi_1grams_"+corpus+"-20140905.db","c") as db:
        with open("resources/grams/OF_klk_fi_1grams_"+corpus+"-20140905", "r", encoding="utf-8" ) as f:
                    for line in f:
                        w = re.split("\t", line)
                        db[w[0]]=w[1]

def get_word_probability(word):
    freqs = []
    for corpus in corpus_sizes:
        with dbm.open("resources/grams/OF_klk_fi_1grams_"+corpus+"-20140905.db") as db:
            freq = int(db.get(word,'0'))+1
        freq = freq/(corpus_sizes[corpus]["types"]+corpus_sizes[corpus]["tokens"])
        freqs.append(freq)
    return sum(freqs)/len(freqs)

def run_list(f, word):

    for line in f:
        w = re.split("\t", line)
        if word == w[0]: return int(w[1])+1

    return 1


def get_new_frag(pos):
    
    z = pos["sub"]
    for j in range(1, len(pos["orig"])): z += "<+>"
    return z


def get_top_100_fragments(fragments):
    
    filtered_fragments = []
    for x in fragments:
        if x not in filtered_fragments: filtered_fragments.append(x)


    fragments = filtered_fragments

    sorted_fragments = sorted(fragments, key=lambda k: k["prob"], reverse=True)
    if len(sorted_fragments) > 100: 

        return sorted_fragments[:100]
    else: 
        
        return sorted_fragments
