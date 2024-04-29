from contextlib import contextmanager
import yaml
from typing import Any, Dict, Union


class RecipeLoader(yaml.BaseLoader):
    @classmethod
    @contextmanager
    def with_namespace(cls, namespace):
        try:
            cls._namespace = namespace
            yield
        finally:
            del cls._namespace

    def construct_sequence(self, node: Any, deep: bool = False) -> Any:
        """deep is True when creating an object/mapping recursively,
        in that case want the underlying elements available during construction
        """
        # find if then else selectors
        for sequence_idx, child_node in enumerate(node.value[:]):
            # if then is only present in MappingNode

            if isinstance(child_node, yaml.MappingNode):
                # iterate to find if there is IF first

                the_evaluated_one = None
                for idx, (key_node, value_node) in enumerate(child_node.value):
                    if key_node.value == "if":
                        # we catch the first one, let's try to find next pair of (then | else)
                        then_node_key, then_node_value = child_node.value[idx + 1]

                        if then_node_key.value != "then":
                            raise ValueError(
                                "cannot have if without then, please reformat your variant file"
                            )

                        try:
                            _, else_node_value = child_node.value[idx + 2]
                        except IndexError:
                            _, else_node_value = None, None

                        to_be_eval = f"{value_node.value}"

                        evaled = eval(to_be_eval, self._namespace)
                        if evaled:
                            the_evaluated_one = then_node_value
                        elif else_node_value:
                            the_evaluated_one = else_node_value

                        if the_evaluated_one:
                            node.value.remove(child_node)
                            node.value.insert(sequence_idx, the_evaluated_one)
                        else:
                            # neither the evaluation or else node is present, so we remove this if
                            node.value.remove(child_node)

        if not isinstance(node, yaml.SequenceNode):
            raise Exception(
                None,
                None,
                f"expected a sequence node, but found {node.id!s}",
                node.start_mark,
            )

        return [self.construct_object(child, deep=deep) for child in node.value]


def load_yaml(content: Union[str, bytes]):
    return yaml.load(content, Loader=yaml.BaseLoader)


def remove_empty_keys(variant_dict):
    filtered_dict = {}
    for key, value in variant_dict.items():
        if isinstance(value, list) and len(value) == 0:
            continue
        filtered_dict[key] = value

    return filtered_dict


def parse_recipe_config_file(path, namespace):
    with open(path) as f:
        with RecipeLoader.with_namespace(namespace):
            content = yaml.load(f, Loader=RecipeLoader)
    return remove_empty_keys(content)


def load_all_requirements(content) -> Dict[str, Any]:
    # with open(path) as f:
    #     content = yaml.load(f, Loader=yaml.BaseLoader)

    requirements_section = dict(content.get("requirements", {}))
    if not requirements_section:
        return {}

    for section in requirements_section:
        section_reqs = requirements_section[section]
        if not section_reqs:
            continue
        expanded_reqs = []
        for req in section_reqs:
            if isinstance(req, dict):
                then_reqs = req.get("then", [])
                else_reqs = req.get("else", [])
                expanded_reqs.extend(then_reqs)
                expanded_reqs.extend(else_reqs)
            else:
                expanded_reqs.append(req)
        requirements_section[section] = expanded_reqs

    return requirements_section
