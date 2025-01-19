(function($) {
    $(document).ready(function() {
        var search_div = $('.grp-change-list #search');
        if (search_div) {
            var reann_url = document.URL + 'reannotate_grammar_all';
            search_div.prepend('<a href="' + reann_url + '" class="grp-button" id="reannotate_button">Reannotate grammar in unchecked</a>');
        };
    });
})(grp.jQuery);
