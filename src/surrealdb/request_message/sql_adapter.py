"""
Defines a class that adapts SQL commands from various sources into a single string.
"""


class SqlAdapter:
    """
    Adapts SQL commands from various sources into a single string.
    """

    @staticmethod
    def from_list(commands: list[str]) -> str:
        """
        Converts a list of SQL commands into a single string.

        :param commands: (list[str]) the list of commands to create the migration from
        :return: (str) a series of SQL commands as a single string
        """
        buffer = []
        for i in commands:
            if i == "":
                pass
            else:
                if i[-1] != ";":
                    i += ";"
                buffer.append(i)
        return " ".join(buffer)

    @staticmethod
    def from_docstring(docstring: str) -> str:
        """
        Creates a single SQL string from a docstring.

        :param docstring: (str) the docstring to create the migration from
        :return: (str) a series of SQL commands as a single string
        """
        buffer = docstring.replace("\n", "").replace("  ", "").split(";")
        final_buffer = []
        for i in buffer:
            if i == "":
                pass
            else:
                final_buffer.append(i + ";")
        return " ".join(final_buffer)

    @staticmethod
    def from_file(file_path: str) -> str:
        """
        Creates a single SQL string from a file.

        :param file_path: (str) the path to the file to create the migration from
        :return: (str) a series of SQL commands as a single string
        """
        buffer = []
        with open(file_path) as file:
            raw_buffer = file.read().split("\n")
            for i in raw_buffer:
                if i == "":
                    pass
                elif i[0:2] == "--":
                    pass
                else:
                    buffer.append(i)
        cleaned_string = " ".join(buffer)
        cleaned_buffer = cleaned_string.split(";")
        final_buffer = []
        for i in cleaned_buffer:
            if i == "":
                pass
            else:
                if i[0] == " ":
                    final_buffer.append(i[1:] + ";")
                else:
                    final_buffer.append(i + ";")
        return " ".join(final_buffer)
