class UtilsMixin:
    @staticmethod
    def check_response_for_error(response: dict, process: str) -> None:
        if response.get("error") is not None:
            raise Exception(response.get("error"))

    @staticmethod
    def check_response_for_result(response: dict, process: str) -> None:
        if "result" not in response.keys():
            raise Exception(f"no result {process}: {response}")
