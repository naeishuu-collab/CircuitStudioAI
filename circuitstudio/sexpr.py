"""Small bounded S-expression reader for KiCad structural checks."""

import json


class SExprError(ValueError):
    pass


def parse_one(text):
    index = 0

    def skip():
        nonlocal index
        while index < len(text):
            if text[index].isspace():
                index += 1
            elif text[index] == ";":
                end = text.find("\n", index)
                index = len(text) if end < 0 else end + 1
            else:
                break

    def parse(depth=0):
        nonlocal index
        if depth > 256:
            raise SExprError("S式のネストが上限256を超えています。")
        skip()
        if index >= len(text):
            raise SExprError("S-expressionが途中で終了しました。")
        if text[index] == "(":
            index += 1
            values = []
            while True:
                skip()
                if index >= len(text):
                    raise SExprError("閉じ括弧がありません。")
                if text[index] == ")":
                    index += 1
                    return values
                values.append(parse(depth + 1))
        if text[index] == ")":
            raise SExprError("対応しない閉じ括弧があります。")
        if text[index] == '"':
            start = index
            index += 1
            escaped = False
            while index < len(text):
                char = text[index]
                index += 1
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    return json.loads(text[start:index])
            raise SExprError("引用文字列が閉じていません。")
        start = index
        while index < len(text) and not text[index].isspace() and text[index] not in "();":
            index += 1
        if start == index:
            raise SExprError("S-expressionのatomが不正です。")
        return text[start:index]

    result = parse()
    skip()
    if index != len(text):
        raise SExprError("S-expressionの後ろに余分なデータがあります。")
    return result


def require_root(text, expected):
    root = parse_one(text)
    if not isinstance(root, list) or not root or root[0] != expected:
        raise SExprError(f"KiCadファイルのルートは ({expected} ...) である必要があります。")
    return root


def children(node, name):
    return [item for item in node if isinstance(item, list) and item and item[0] == name]
