import subprocess
import argparse
import json
import re

def calculate_mi_marks(rank):
    """
    Calculate marks based on the Maintainability Index (MI) rank.
    """
    match rank:
        case 'A' | 'B':
            return 1
        case 'C':
            return 0.75
        case 'D':
            return 0.5
        case 'E':
            return 0.25
        case _:
            return 0.1

def calculate_cc_marks(average_complexity_grade):
    """
    Calculate marks based on Cyclomatic Complexity grade.
    """
    match average_complexity_grade:
        case 'A' | 'B':  
            return 1
        case 'C': 
            return 0.75
        case 'D': 
            return 0.5
        case 'E':  
            return 0.25
        case _: 
            return 0.1
def calculate_comments_marks(comments_ratio): 
    """
    Calculate marks based on the comments ratio.
    """
    match comments_ratio:
        case ratio if ratio >= 0.15:
            return 0.5
        case ratio if ratio >= 0.10:
            return 0.45
        case ratio if ratio >= 0.05:
            return 0.35
        case ratio if ratio >= 0.02:
            return 0.25
        case _:
            return 0.1
        
def calculate_pylint_marks(pylint_rating):
    """
    Calculate marks based on Pylint rating out of 10.
    """
    pylint_rating = round(pylint_rating, 1)

    match pylint_rating:
        case rating if rating >= 8:
            return 2.5  
        case rating if rating >= 7:
            return 2
        case rating if rating >= 5:
            return 1.5 
        case rating if rating >= 3:
            return 1
        case rating if rating >= 1:
            return 0.5 
        case _:
            return 0.25
def strip_ansi_codes(text):
    """
    Removes ANSI color codes from the given text.
    """
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def run_command(command):
    """
    Runs a subprocess command, displays output to the screen, and captures it.
    """
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = process.communicate()

    print(stdout, end="")
    print(stderr, end="")

    return stdout, stderr


def check_pylint(file_path):
    """Runs Pylint on the given file and reports the modularity rating.

    Args:
        file_path (str): The path to the Python file to be checked.

    Returns:
        float: The code quality rating of the file as reported by Pylint. 
               If the rating cannot be determined, returns 0."""

    command = ['pylint', file_path]
    stdout, _ = run_command(command)

    rating_match = re.search(r'Your code has been rated at ([\d\.]+)/10', stdout)
    if rating_match:
        rating = float(rating_match.group(1))
    else:
        rating = 0

    return rating


def check_radon(file_path):
    """ Runs Radon on the given file and reports cyclomatic complexity and maintainability index.
    Parameters:
    file_path (str): The path to the file to be analyzed.
    Returns:
    dict: A dictionary containing the following keys:
        - 'mi' (int): The maintainability index of the file.
        - 'rank' (str): The maintainability rank of the file.
        - 'cc_grade' (str): The cyclomatic complexity grade of the file.
        - 'cc_score' (float): The cyclomatic complexity score of the file.
    """

    command_cc = ['radon', 'cc', '-s', '--total-average', file_path] # -s for summary and --total-average for average
    stdout_cc, _ = run_command(command_cc)

    cleaned_result = strip_ansi_codes(stdout_cc)
    average_match = re.search(r'Average complexity: ([A-F]) \((\d+\.?\d*)\)', cleaned_result)
    if average_match:
        grade = average_match.group(1)
        score = float(average_match.group(2))
    else:
        grade = 'F'
        score = 0

    command_mi = ['radon', 'mi', '-s', '-j', file_path] # -s for summary and -j for json output
    stdout_mi, _ = run_command(command_mi)
     
    output = json.loads(stdout_mi)
    file_key = list(output.keys())[0] # the outputed nested json object has a key that is the file path and value is the analysis
    mi = output[file_key]['mi'] if 'mi' in output[file_key] else 0
    rank = output[file_key]['rank'] if 'rank' in output[file_key] else 'F'
    
    command_comments = ['radon', 'raw', '-j', file_path] # -j for json output
    stdout_comments, _ = run_command(command_comments)
    output_comments = json.loads(stdout_comments)
    file_key_comments = list(output_comments.keys())[0]
    
    sloc = output_comments[file_key_comments]['sloc']
    comments = output_comments[file_key_comments]['comments']
    ratio = comments / sloc if sloc > 0 else 0

    return {'mi': mi, 'rank': rank, 'cc_grade': grade, 'cc_score': score, 'comments_ratio': ratio}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check Python code for naming conventions and modularity issues.")
    parser.add_argument('file_paths', nargs='+', help="Path to one or more Python files to be checked.")
    args = parser.parse_args()

    # total marks for all files
    total_scores = 0
    total_files = len(args.file_paths)
    
    total_mi_marks = 1
    total_cc_marks = 1
    total_pylint_marks = 2.5
    total_comments_marks = 0.5
    total_marks = total_mi_marks + total_cc_marks + total_pylint_marks + total_comments_marks

    for file_path in args.file_paths:
        print(f"Processing: {file_path}")
        try:
            pylint_issues = check_pylint(file_path)
            scores = check_radon(file_path)
            
            mi_marks = calculate_mi_marks(scores['rank'])
            cc_marks = calculate_cc_marks(scores['cc_grade'])
            comments_marks = calculate_comments_marks(scores['comments_ratio'])
            pylint_marks = calculate_pylint_marks(pylint_issues)
            
            final_score = mi_marks + cc_marks + pylint_marks + comments_marks
            total_scores += final_score
            
            print(f"Results for {file_path}:")
            print(f"  Modularity: {mi_marks}/{total_mi_marks}")
            print(f"  Cyclomatic Complexity: {cc_marks}/{total_cc_marks}")
            print(f"  Pylint Rating: {pylint_marks}/{total_pylint_marks}")
            print(f"  Comments Ratio: {comments_marks}/{total_comments_marks}")
            print(f"  Total score: {final_score}/{total_marks}\n")
        
        except Exception as e:
            print(f"Error processing {file_path}: {e}\n")
            total_files -= 1  # adjust total files if there's an error

    if total_files > 0:
        average_score = total_scores / total_files
        print(f"Average Score for {total_files} file(s): {average_score}/{total_marks}")
    else:
        print("No valid files processed.")
