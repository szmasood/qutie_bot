import argparse
import glob
import json
import os
import pytesseract
import requests

from collections import Counter
from nltk.corpus import stopwords
from PIL import Image, ImageEnhance


def setup_args():
    """
    Setup args
    :return: api_key, search_id, desktop_path
    """
    parser = argparse.ArgumentParser(description='HQ Bot lel')
    parser.add_argument('--g_api_key', help='Google Custom Search API key')
    parser.add_argument('--search_id', help='Google Custom Search Engine ID')
    parser.add_argument('--desktop_path', help='Path to desktop')

    args = parser.parse_args()

    return args.g_api_key, args.search_id, args.desktop_path


def enhance_image(img_path):
    """
    Brighten, sharpen, increase contrast, make it gray-scale and return image
    :param img_path: path to image
    :return: img object
    """
    img = Image.open(img_path)

    brighten = ImageEnhance.Brightness(img).enhance(1)
    contrast = ImageEnhance.Contrast(brighten).enhance(3)
    sharpen = ImageEnhance.Sharpness(contrast).enhance(4)

    # Gray-scale
    img = sharpen.convert("L")
    #img.show()
    return img


def remove_stop_words(l):
    """
    Remove stop words from list of words
    :param l: list of words
    :return: sentence string with stopwords removed
    """
    return ' '.join(list(filter(lambda x: x not in stop_words, l)))


def get_question_answers(enhanced_img):
    """
    Apply OCR and detect question + answers
    :param enhanced_img: image object
    :return: question with stopwords removed and list of answers
    """
    text = pytesseract.image_to_string(enhanced_img)

    split_text = text.split("\n\n")
    split_text = split_text[1:] if len(split_text[0]) < 10 else split_text
    question = split_text[0].replace('\n', ' ')
    answers = split_text[1:]

    # Sometimes answers have newlines
    lines = []
    for line in answers:
        a = line.split('\n')
        for answer in a:
            lines.append(answer)

    answers = lines
    question_cleaned = remove_stop_words(question.split(' '))
    return question_cleaned, answers


def get_search_results(api_key, api_base, cx, query):
    """
    Search google custom search API for question and search through snippets
    :param api_key: key for google custom search api
    :param api_base: base uri for google custom search
    :param cx: custom search id
    :param query: query to be searched
    :return: snippets with stop words removed
    """
    parameters = {'key': api_key,
                  'cx': cx,
                  'q': query}
    request = requests.get(api_base, params=parameters)
    data = json.loads(request.content)
    snippets = [item['snippet'].replace('\n', '') for item in data['items']]
    snippets = [remove_stop_words(snippet.split(' ')) for snippet in snippets]
    return snippets


def occurrence_pct(search_results, answers):
    """
    Count occurrences of answers in search results
    :param search_results: list of top search results
    :param answers: list of answers from OCR
    :return: List of answers with respective percentage of occurrence over unique search results
    """
    words = [word.lower() for line in search_results for word in line.split()]
    count_histo = Counter(words)
    num_words = len(count_histo)

    results = []

    for answer in answers:
        if answer in count_histo:
            results.append((answer, (float(count_histo[answer])/num_words) * 100))

    return sorted(results, key=lambda x: x[1], reverse=True) if results else [('',0)]


def get_weighted_results(question_results, answer_results, answers):
    """
    Weight results based on querying with just question, and querying with question + answers
    :param question_results: results from just querying question
    :param answer_results: results from querying questions + answers
    :param answers: list of answers from OCR
    :return: dumb heuristic weighted answers and occurrences
    """
    dict_question_results = dict(question_results)
    dict_answer_results = dict(answer_results)

    weighted_results = []
    for answer in answers:
        weighted = 0
        if answer in dict_question_results and answer in dict_answer_results:
            weighted = dict_question_results[answer] * 0.65 + dict_answer_results[answer] * 0.35
        else:
            if answer in dict_answer_results:
                weighted = dict_answer_results[answer]
        weighted_results.append((answer, weighted))

    return sorted(weighted_results, key=lambda x: x[1], reverse=True)


def run(search_api_key, search_api_base, cx, ss_path):
    """
    Run OCR + Search and print results
    :param search_api_key: Google Custom Search API key
    :param search_api_base: Google Custom Search Base URI
    :param cx: Google Custom Search id
    :param ss_path: screenshot path
    :return:
    """
    enhanced_image = enhance_image(ss_path)
    question, answers = get_question_answers(enhanced_image)

    print(question)
    print(answers)
    print()

    question_query = get_search_results(search_api_key, search_api_base, cx, question)
    question_query_results = occurrence_pct(question_query, answers)

    print('Results with just question')
    print(question_query_results)
    print()

    answer_query = get_search_results(search_api_key, search_api_base, cx, '{} {}'.format(question, ' '.join(answers)))
    answer_query_results = occurrence_pct(answer_query, answers)

    weighted_results = get_weighted_results(question_query_results, answer_query_results, answers)

    print('Results with question + answers')
    print(weighted_results)


if __name__ == '__main__':
    search_api_key, cx, desktop_base = setup_args()
    search_api_base = 'https://www.googleapis.com/customsearch/v1?'

    stop_words = set(stopwords.words('english')) - {'not', 'non'}

    question_num = 1
    while True:
        ss_path = glob.glob("{}/{}".format(desktop_base, "*.png"))
        if ss_path:
            run(search_api_key, search_api_base, cx, ss_path[0])
            os.rename(ss_path[0], "{}/{}/{}".format(desktop_base, 'hq', question_num))
            question_num += 1
