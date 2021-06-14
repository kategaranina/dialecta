(function($) {
    $(document).ready(function() {
        var search_div = $('.grp-change-list #search');
        if (search_div) {
            var search_url = document.URL + 'search';
            search_div.prepend('<a href="' + search_url + '" class="grp-button" id="search_button">Advanced search</a>');
        };
    });
})(grp.jQuery);
