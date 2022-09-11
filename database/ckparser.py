# coding: utf-8
import ast
import datetime
import json
import logging
import os
import re
import sys

# Try to import chardet for encoding detection
try:
    from chardet import detect
except ImportError:
    detect = None


# Logger (because logging is awesome)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
# formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.INFO)
# console_handler.setFormatter(formatter)
# logger.addHandler(console_handler)
# file_handler = logging.FileHandler("parser.log")
# file_handler.setLevel(logging.INFO)
# file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)


# Boolean transformation
booleans = {"yes": True, "no": False}
# Tags with must be aggregate as a list in JSON (don't hesitate to add more if needed)
forced_list_keys = (
    # "if", "else_if", "else", "not", "or", "and", "nor", "nand", "root", "from", "prev",
)
# Special keywords
keywords = ("scripted_trigger", "scripted_effect")
# Variables collected in files
variables = {}


# Regex to find and replace quoted string
regex_string = re.compile(r"\"[^\"\n]*\"")
regex_string_multiline = re.compile(r"\"[^\"]*\"", re.MULTILINE)
# Regex to remove comments in files
regex_comment = re.compile(r"##*(?P<comment>.*)\s*$", re.MULTILINE)
# Regex for fixing blocks with no equal sign
regex_block = re.compile(r"^([^\s\{\=]+)\s*\{\s*$", re.MULTILINE)
# Regex to remove "list" prefix
regex_list = re.compile(r"\s*=\s*list\s*([\{\"\|])", re.MULTILINE)
# Regex for color blocks (color = [rgb|hsv] { x y z })
regex_color = re.compile(r"=\s*(?P<type>\w+)\s*{")
# Regex to parse items with format key=value
regex_inline = re.compile(r"([^\s]+\s*[!<=>]+\s*(((?![@\"])\[?[^\s]+\]?)|(\"[^\"]+\")|(@\[[^\]]+\]))|(@\w+))")
# Regex to parse blocks with bracket below the key
regex_values = re.compile(r"(=\s*\n+)|(\n+\s*=)")
# Regex to parse lines with format key=value
regex_line = re.compile(r"(?P<key>[^\s]+)\s*(?P<operator>[!<=>]+)\s*(list\s*)?(?P<value>.*)")
# Regex to parse independent items in a list
regex_item = re.compile(r"(\"[^\"]+\"|[\d\.]+|[^\s]+)")
# Regex to remove empty lines
regex_empty = re.compile(r"(\n\s*\n)+", re.MULTILINE)
# Regex to parse locale files
regex_locale = re.compile(r"^\s*(?P<key>[^\:#]+)\:\d+\s\"(?P<value>.+)\"\s*$")


def read_file(path, encoding="utf_8_sig"):
    """
    Try to read file with encoding
    If chardet is installed, encoding will be automatically detected
    :param path: Path to file
    :param encoding: Encoding
    :return: File content
    """
    if not os.path.exists(path) or not os.path.isfile(path):
        return
    if detect:
        with open(path, "rb") as file:
            raw_data = file.read()
        if result := detect(raw_data):
            encoding = result["encoding"]
            logger.debug(f"Detected encoding: {result['encoding']} ({result['confidence']:0.0%})")
        del raw_data
    with open(path, encoding=encoding) as file:
        return file.read()


def parse_text(text, return_text_on_error=False, filename=None):
    """
    Parse raw text
    :param text: Text to parse
    :param return_text_on_error: (default false) Return working text document if parsing fails
    :param filename: (default none) Filename (only for debugging)
    :return: Parsed data as dictionary
    """
    root = {}
    nodes = [("", root)]
    local_variables = {}
    # Cleaning document
    strings, index = {}, 0
    for index, match in enumerate(regex_string.finditer(text)):
        strings[index] = match.group(0)
        text = text.replace(match.group(0), f"|{index}|", 1)
    text = regex_comment.sub("", text)
    for index, match in enumerate(regex_string_multiline.finditer(text), start=index + 1):
        strings[index] = match.group(0).replace("\n", " ").strip()
        text = text.replace(match.group(0), f"|{index}|", 1)
    text = regex_list.sub("|list=\g<1>", text)
    text = regex_list.sub("|list=\g<1>", text)
    text = regex_block.sub("\g<1>={", text)
    text = text.replace("{", "\n{\n").replace("}", "\n}\n")
    text = regex_color.sub("={\n\g<1>", text)
    text = regex_inline.sub("\g<1>\n", text)
    text = regex_values.sub("=", text)
    text = regex_empty.sub("\n", text)
    for keyword in keywords:
        text = text.replace(f"{keyword} ", f"{keyword}|")
    for index, string in strings.items():
        text = text.replace(f"|{index}|", string, 1)
    del strings
    # Parsing document line by line
    for line_number, line_text in enumerate(text.splitlines(), start=1):
        try:
            line_text = line_text.strip()
            # Nothing to do if line is empty
            if not line_text:
                continue
            # Get the current node
            node_name, node = nodes[-1]
            # If line is key=value
            if match := regex_line.fullmatch(line_text):
                key, operator, _, value = match.groups()
                value = value.strip()
                # If value is a new block
                if value.endswith("{"):
                    item = {}
                    # If key is duplicate with inner block
                    if key in node:
                        if not isinstance(node[key], list):
                            node[key] = [node[key]]
                        node[key].append(item)
                    # If this block name must be forced as list
                    elif key.lower() in forced_list_keys:
                        node[key] = [item]
                    elif isinstance(node, list):  # Only for on_actions...
                        node.append(item)
                    else:
                        node[key] = item
                    # Change current node for next lines
                    nodes.append((key, item))
                    continue
                elif value.lower() in booleans:
                    # Convert to boolean
                    value = booleans[value]
                else:
                    # Try to convert value to Python value
                    try:
                        value = ast.literal_eval(value)
                    except:
                        pass
                # If key is duplicate with direct value
                if key in node:
                    if node[key] != value:  # Avoid single duplicates
                        if not isinstance(node[key], list):
                            node[key] = [node[key]]
                        node[key].append(value)
                # If this key must be forced as list
                elif key.lower() in forced_list_keys:
                    node[key] = [value]
                else:
                    # If operator is not equal
                    if operator != "=":
                        node[key] = {
                            "@operator": operator,
                            "@value": value,
                        }
                        if isinstance(value, str) and (value.startswith("@") or value in variables):
                            node[key]["@value"] = {
                                "@type": "variable",
                                "@value": value,
                                "@result": variables.get(value.lstrip("@")),
                            }
                    # If value is a formula
                    elif isinstance(value, str):
                        if value.startswith("@[") and value.endswith("]"):
                            formula = value.lstrip("@[").rstrip("]")
                            for var_name, var_value in variables.items():
                                formula = re.sub(rf"\b{var_name}\b", str(var_value), formula)
                            try:
                                result = eval(formula, None, variables)
                            except:
                                result = None
                            if isinstance(result, float):
                                result = round(result, 5)
                            node[key] = {
                                "@type": "formula",
                                "@value": value,
                                "@result": result,
                            }
                            if result:  # and key.startswith("@"):
                                variable_name = key.lstrip("@")
                                variables[variable_name] = local_variables[variable_name] = result
                        elif value.startswith("@"):
                            node[key] = {
                                "@type": "variable",
                                "@value": value,
                                "@result": variables.get(value.lstrip("@")),
                            }
                        elif variable_value := variables.get(value):
                            if not isinstance(variable_value, str):
                                node[key] = {
                                    "@type": "variable",
                                    "@value": value,
                                    "@result": variable_value,
                                }
                                if value and key.startswith("@"):
                                    variable_name = key.lstrip("@")
                                    variables[variable_name] = local_variables[variable_name] = value
                        else:
                            node[key] = value
                            if value and key.startswith("@"):
                                variable_name = key.lstrip("@")
                                variables[variable_name] = local_variables[variable_name] = value
                    else:
                        node[key] = value
                        if value and key.startswith("@"):
                            variable_name = key.lstrip("@")
                            variables[variable_name] = local_variables[variable_name] = value
            # If line is closing block
            elif line_text == "}":
                # Return to previous node
                nodes.pop()
            # If line is a list or list item
            else:
                # Ensure previous data are treated as list
                if not isinstance(node, list):
                    _, prev = nodes[-2]
                    if node_name:
                        prev[node_name] = node = []
                    elif isinstance(prev, list):
                        prev[-1] = node = []
                    nodes[-1] = (node_name, node)
                # If list is composed of blocks
                if line_text == "{":
                    item = {}
                    node.append(item)
                    nodes.append(("", item))
                # Or if list is composed of plain values
                else:
                    # Find every couple of key=value
                    for item in regex_item.findall(line_text):
                        if item.startswith("@"):
                            node.append(
                                {
                                    "@type": "variable",
                                    "@value": item,
                                    "@result": variables.get(item.lstrip("@")),
                                }
                            )
                        else:
                            try:
                                node.append(ast.literal_eval(item))
                            except:
                                node.append(item)
        except Exception as error:
            if filename:
                logger.warning(f"Filename: {filename}")
            logger.warning(f"Line {line_number}: {line_text}")
            logger.error(f"Parse error: {error}")
            return text if return_text_on_error else None
    return root


def parse_file(path, output_dir=None, encoding="utf_8_sig", base_dir=None, save=True):
    """
    Parse file
    :param path: Path to file to parse
    :param output_dir: Directory where to save parsed file
    :param encoding: Encoding used to read file
    :param base_dir: Base directory (for debug)
    :param save: (default false) Save parsed file in output_directory
    :return: Parsed data as dictionary or text if parsing fails
    """
    start_time = datetime.datetime.utcnow()
    if base_dir:
        base_dir = os.sep.join(base_dir.rstrip(os.sep).split(os.sep)[:-1]) + os.sep
        base_dir = os.path.dirname(path.replace(base_dir, ""))
    if not base_dir:
        base_dir = os.path.dirname(path).split(os.sep)[-1]
    text = read_file(path, encoding)
    if not text.strip():
        return None
    filename = os.path.join(base_dir, os.path.basename(path))
    logger.debug(f"Parsing {filename}")
    data = parse_text(text, return_text_on_error=True, filename=filename)
    if save:
        filename, _ = os.path.splitext(os.path.basename(path))
        directory = os.path.join(output_dir or "output", *base_dir.split(os.sep))
        os.makedirs(directory, exist_ok=True)
        if not isinstance(data, dict):
            filename = os.path.join(directory, filename + ".error")
            with open(filename, "w") as file:
                file.write(data)
        else:
            filename = os.path.join(directory, filename + ".json")
            with open(filename, "w") as file:
                json.dump(data, file, indent=4)
    total_time = (datetime.datetime.utcnow() - start_time).total_seconds()
    logger.debug(f"Elapsed time: {total_time:0.3}s!")
    return data


def parse_all_files(path, output_dir=None, encoding="utf_8_sig", keep_data=False, save=True, variables_first=True):
    """
    Parse all text files in a directory
    :param path: Path where to find files to parse
    :param output_dir: Directory where to save parsed files
    :param encoding: Encoding used to read files
    :param keep_data: (default false) Return parsed data of all files in a dictionary
    :param save: Save every parsed data in output directory
    :param variables_first: Try to parse variables first
    :return: Dictionary (key: file, value: parsed data if keep_data=True)
    """
    start_time = datetime.datetime.utcnow()
    success, errors = {}, []
    for loop in range(2):
        for current_path, _, all_files in os.walk(path):
            if variables_first:
                if not loop and not current_path.endswith("script_values"):
                    continue
            for filename in all_files:
                if not filename.lower().endswith(".txt"):
                    continue
                filepath = os.path.join(current_path, filename)
                data = parse_file(filepath, output_dir=output_dir, encoding=encoding, base_dir=path, save=save)
                if isinstance(data, str):
                    errors.append(filepath)
                    continue
                filepath = filepath.replace(path, "").replace(os.sep, "/").lstrip("/").rstrip(".txt")
                success[filepath] = data if keep_data else True
        if not variables_first:
            break
    total_time = (datetime.datetime.utcnow() - start_time).total_seconds()
    logger.info(f"{len(success)} parsed file(s) and {len(errors)} errors in {total_time:0.3f}s!")
    for error in errors:
        logger.warning(f"Error detected in: {error}")
    return success


def parse_all_locales(path, encoding="utf_8_sig", language="english"):
    """
    Parse all locales strings
    :param path: Path where to find locale files
    :param encoding: Encoding for reading files
    :param language: Target language
    :return: Locales in dictionary
    """
    locales = {}
    for current_path, _, all_files in os.walk(path):
        for filename in all_files:
            if not filename.lower().endswith(".yml"):
                continue
            filepath = os.path.join(current_path, filename)
            with open(filepath, encoding=encoding) as file:
                header = file.readline()
                if language not in header:
                    continue
                for line in file:
                    if match := regex_locale.match(line):
                        key, value = match.groups()
                        locales[key] = value
    return locales


def walk(obj, from_key=None):
    """
    Walk through a complex dictionary struct
    :param obj: Dictionary
    :param from_key: (only used by recursion) Key of the parent section
    :return: Yield key and value during iteration
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from walk(value, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item, from_key)
    else:
        yield from_key, obj


# Tags which are always a list
list_keys_rules = [
    # Colors
    re.compile(r"^\w+_color$", re.IGNORECASE),
    re.compile(r"^color\w*$", re.IGNORECASE),
    # DNA
    re.compile(r"^gene_\w+$", re.IGNORECASE),
    re.compile(r"^face_detail_\w+$", re.IGNORECASE),
    re.compile(r"^expression_\w+$", re.IGNORECASE),
    re.compile(r"^\w+_accessory$", re.IGNORECASE),
    re.compile(r"^complexion$", re.IGNORECASE),
    # Plural keys
    re.compile(r"^(?!(e_|k_|d_|c_|b_))[^\.\:\s]+s$", re.IGNORECASE),
    # GFX
    re.compile(r"^\w+_gfx$", re.IGNORECASE),
    # Object=
    re.compile(r"^[^=]+=$", re.IGNORECASE),
]


def revert(obj, from_key=None, prev_key=None, depth=-1):
    """
    /!\\ Work in progress /!\\
    Try to revert a dict-struct to Paradox format
    :param obj: Dictionary
    :param from_key: (only used by recursion) Key of the parent section
    :param prev_key: (only used by recursion) Key of the great-parent section
    :param depth: (only used by recursion) Depth of the current section
    :return: Text
    """
    lines = []
    sep = " " * 4
    tab = sep * depth
    if isinstance(obj, dict):
        if special := revert_special(obj, from_key):
            lines.append(f"{tab}{special}")
        else:
            if from_key:
                from_key = from_key.replace("|", " ")
                lines.append(f"{tab}{from_key} = {{")
            elif depth > 0:
                lines.append(f"{tab}{{")
            for key, value in obj.items():
                lines.extend(revert(value, from_key=key, prev_key=from_key, depth=depth + 1))
            if from_key or depth > 0:
                lines.append(f"{tab}}}")
    elif isinstance(obj, list):
        is_list = None
        # Only for colors
        if from_key and isinstance(obj, list) and len(obj) > 3 and obj[0] in ("rgb", "hsv", "hls", "hsv360"):
            from_key = f"{from_key} {obj[0]}"
            obj = obj[1:]
            is_list = True
        if from_key and not is_list and not any(regex.match(from_key) for regex in list_keys_rules):
            for value in obj:
                lines.extend(revert(value, from_key=from_key, prev_key=prev_key, depth=depth))
        else:
            if from_key:
                key = from_key.replace("|", " ")
                lines.append(f"{tab}{key} = {{")
            else:
                lines.append(f"{tab}{{")
            for value in obj:
                lines.extend(revert(value, depth=depth + 1))
            lines.append(f"{tab}}}")
    elif isinstance(obj, (int, float)) or obj:
        if from_key:
            from_key = from_key.replace("|", " ")
            lines.append(f"{tab}{from_key} = {revert_value(obj, from_key, prev_key)}")
        else:
            lines.append(f"{tab}{revert_value(obj)}")
    if depth < 0:
        return "\n".join(lines)
    return lines


def revert_value(value, from_key=None, prev_key=None):
    """
    /!\\ Work in progress /!\\
    Revert values utility for revert function
    :param value: Value to revert
    :param from_key: Key of the parent section
    :param prev_key: Key of the great-parent section
    :return: Reverted value
    """
    if isinstance(value, bool):
        return "yes" if value else "no"
    elif isinstance(value, str):
        if " " in value or (value.startswith("$") and value.endswith("$")) or from_key == "name":
            value = value.replace('"', '\\"')
            return f'"{value}"'
    return value


def revert_special(obj, from_key=None):
    """
    /!\\ Work in progress /!\\
    Revert special values utility for revert function
    :param obj: Special object to revert
    :param from_key: Key of the parent section
    :return: Reverted object
    """
    if "@operator" in obj:
        operator, value = obj["@operator"], obj["@value"]
        return f"{from_key} {operator} {revert_value(value, from_key)}"
    elif "@type" in obj:
        value, result = obj["@value"], obj["@result"]
        return f"{from_key or value} = {value}"


def load_variables():
    """
    Load variables from a local file variables.json
    """
    global variables
    if not os.path.exists("variables.json"):
        return
    with open("_variables.json") as file:
        variables = json.load(file)


def save_variables():
    """
    Save variables in local file variables.json
    """
    if not variables:
        return
    with open("_variables.json", "w") as file:
        json.dump(variables, file, indent=4, sort_keys=True)


if __name__ == "__main__":
    if 2 > len(sys.argv) > 4:
        logger.info("Usage: python ckparser.py <directory or file> [<output directory>] [<encoding: utf_8_sig>]")
        sys.exit(0)
    load_variables()
    if os.path.isdir(sys.argv[1]):
        parse_all_files(*sys.argv[1:])
    else:
        parse_file(*sys.argv[1:], save=True)
    save_variables()
