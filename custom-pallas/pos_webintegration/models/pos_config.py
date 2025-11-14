from odoo import fields, models, api
from odoo.addons.portal.controllers.portal import pager



class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def pager(self, url, total, page=1, step=30, scope=5, url_args=None):
        return pager(url, total, page=page, step=step, scope=scope, url_args=url_args)

    def _search_get_details(self, search_type, order, options):
        """
        Returns indications on how to perform the searches

        :param search_type: type of search
        :param order: order in which the results are to be returned
        :param options: search options

        :return: list of search details obtained from the `website.searchable.mixin`'s `_search_get_detail()`
        """
        result = []
        if search_type in ['pages', 'all']:
            result.append(self.env['website.page']._search_get_detail(self, order, options))
        return result

    def _search_find_fuzzy_term(self, search_details, search, limit=1000, word_list=None):
        """
        Returns the "closest" match of the search parameter within available words.

        :param search_details: obtained from `_search_get_details()`
        :param search: search term to which words must be matched against
        :param limit: maximum number of records fetched per model to build the word list
        :param word_list: if specified, this list of words is used as possible targets instead of
            the words contained in the match fields of each involved model

        :return: term on which a search can be performed instead of the initial search
        """
        # No fuzzy search for less that 4 characters, multi-words nor 80%+ numbers.
        if len(search) < 4 or ' ' in search or len(re.findall(r'\d', search)) / len(search) >= 0.8:
            return search
        search = search.lower()
        words = set()
        best_score = 0
        best_word = None
        enumerate_words = self._trigram_enumerate_words if self.env.registry.has_trigram else self._basic_enumerate_words
        for word in word_list or enumerate_words(search_details, search, limit):
            if search in word:
                return search
            if word[0] == search[0] and word not in words:
                similarity = similarity_score(search, word)
                if similarity > best_score:
                    best_score = similarity
                    best_word = word
                words.add(word)
        return best_word

    def _search_exact(self, search_details, search, limit, order):
        """
        Performs a search with a search text

        :param search_details: see :meth:`_search_get_details`
        :param search: text against which to match results
        :param limit: maximum number of results per model type involved in the result
        :param order: order on which to sort results within a model type

        :return: tuple containing:
            - total number of results across all involved models
            - list of results per model made of:
                - initial search_detail for the model
                - count: number of results for the model
                - results: model list equivalent to a `model.search()`
        """
        all_results = []
        total_count = 0
        for search_detail in search_details:
            model = self.env[search_detail['model']]
            results, count = model._search_fetch(search_detail, search, limit, order)
            search_detail['results'] = results
            total_count += count
            search_detail['count'] = count
            all_results.append(search_detail)
        return total_count, all_results

    def _search_with_fuzzy(self, search_type, search, limit, order, options):
        """
        Performs a search with a search text or with a resembling word

        :param search_type: indicates what to search within, 'all' matches all available types
        :param search: text against which to match results
        :param limit: maximum number of results per model type involved in the result
        :param order: order on which to sort results within a model type
        :param options: search options from the submitted form containing:
            - allowFuzzy: boolean indicating whether the fuzzy matching must be done
            - other options used by `_search_get_details()`

        :return: tuple containing:
            - count: total number of results across all involved models
            - results: list of results per model (see _search_exact)
            - fuzzy_term: similar word against which results were obtained, indicates there were
                no results for the initially requested search
        """
        fuzzy_term = False
        search_details = self._search_get_details(search_type, order, options)
        if search and options.get('allowFuzzy', True):
            fuzzy_term = self._search_find_fuzzy_term(search_details, search)
            if fuzzy_term:
                count, results = self._search_exact(search_details, fuzzy_term, limit, order)
                if fuzzy_term.lower() == search.lower():
                    fuzzy_term = False
            else:
                count, results = self._search_exact(search_details, search, limit, order)
        else:
            count, results = self._search_exact(search_details, search, limit, order)
        return count, results, fuzzy_term