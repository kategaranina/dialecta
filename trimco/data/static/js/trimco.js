(function($) {
    var processing_request = false;
    var prev_page_info = {}

    function ajax_request(req_type, req_data, search=false) {  // TODO: req_type to different funcs?
        if (processing_request == true) {
            console.log('processing previous request, please wait'); // Error to log
            return false;
        };
        processing_request = true;

        var url = "../../ajax/";
        if (search) { url = "../ajax_search/" };

        $.ajax({  //Call ajax function sending the option loaded
            url: url,  //This is the url of the ajax view where you make the search
            //contentType: "application/json; charset=utf-8",
            type: 'POST',
            async: false,
            data: {'request_type' : req_type, 'request_data' : req_data},
            timeout: 300000,
            tryCount : 0,
            retryLimit : 3,
            error: function(x, t, m) {
                this.tryCount++;
                if (x.status == 409 & this.tryCount <= this.retryLimit) {
                    var self = this;
                    var retry = function () { $.ajax(self); }
                    setTimeout(retry, 10000);
                    return;
                }

                console.log(x, t, m);
                alert('Something went wrong. Try again later. If the error persists, please contact developers and describe the problem.')
                processing_request = false;
                if (req_type == 'save_elan_req') {
                    $('#save_to_file').removeClass('fa-spinner off').addClass('fa-floppy-o');
                };
            },
            success: function(response) {
                result = $.parseJSON(response);  // Get the results sent from ajax to here
                processing_request = false
                if (result.error) { // If the function fails
                    console.log(result.error_text); // Error to log
                } else {
                    if (req_type == 'trt_annot_req') {
                        if (req_data['mode'] == 'manual') {
                            list_normlz_suggestions(result.result)
                        }
                        if (req_data['mode'] == 'auto') {
                            // todo: is it actually broken?
                            if (result.result!=null) {
                                apply_auto_annotation(result.result[0],result.result[1],result.result[2])
                            }
                            else {
                                /* continuing to next token when empty*/
                                var next = nextInDOM('trt', $('trt.focused'));
                                if (next) {activate_trt(next)};
                            };
                        }
                    }
                    else if (req_type == 'annot_suggest_req') {
                        list_annot_suggestions(result.result);
                    }
                    else if (req_type == 'save_elan_req') {
                        $('#save_to_file').removeClass('fa-spinner off').addClass('fa-floppy-o');
                    }
                    else if (req_type == 'search') {
                        $('#replace_warning').show();
                        $('#search_result').html(result.result);
                        prev_page_info = result.page_info;
                        if (result.total_pages != null) {
                            construct_page_section(1, result.total_pages);
                        };
                        $('#search_button').html('Search');
                        adjust_DOM_spacing();
                        $(".audiofragment .fa-spinner").removeClass('fa-spinner off').addClass('fa-play');
                    }
                }
            }
        });
    };

    function auto_annotation_request(trt_tag) {
        ajax_request('trt_annot_req', {'trt' : trt_tag.text(), 'mode' : 'auto',});
    };

    function wb_annotation_mode () {
        $( "#workbench" ).removeClass( "wb_reduced", 500, "easeOutBounce");
        $('#wb_col_1').children().attr('style', 'pointer-events: none;opacity: 0.4;');
    };
    function wb_normlization_mode () {
        $('#annotation_suggestions_lst').empty();
        $('#wb_col_1').children().removeAttr('style');
        $( "#workbench" ).addClass( "wb_reduced", 500, "easeOutBounce");
    };

    function activate_trt(trt_tag, search=false) {
        /* prepering <trt> for (re)suggestion of <nrm> */
        var mode = 'manual';
        if ($('#auto_annotation').is(':checked')) {var mode = 'auto'};

        if (mode=='manual') {
            $('#normalization_suggestions_lst').empty();
            $('#normalization_input').val('');
            wb_normlization_mode();
        };
        $('trt.focused').removeAttr('id');
        $('trt').removeClass('focused');
        trt_tag.addClass('focused');
        if (mode=='manual') {
            $('#examined_transcript').text(trt_tag.text());
            var params = {
                'trt': trt_tag.text(),
                'nrm': trt_tag.parent().find('nrm').text(),
                'mode': 'manual',
                'dialect': trt_tag.closest('.annot').attr('dialect')
            };
            ajax_request('trt_annot_req', params, search=search);
        };
        if (mode=='auto') {
            auto_annotation_request(trt_tag)
        }
    };

    function apply_auto_annotation(token, normalization, annotation) {
        console.log($.now(), token, normalization, annotation);

        var norm_tag = $('<nrm>'+normalization+'</nrm>');
        var lemma_tag = $('<lemma>'+annotation[0][0]+'</lemma>');
        var morph_tag = $('<morph>'+annotation[0][1]+'</morph></info>');
        set_annotation(norm_tag, lemma_tag, morph_tag, 'auto')

        /* FROM TAG */
        //var norm_tag = $('<nrm>'+$('#normalization_input').val()+'</nrm>');
        //var lemma_tag = $('<lemma>'+$('#annotation_suggestions_lst li.selected .lemma_suggestion' ).text()+'</lemma>');
        //var morph_tag = $('<morph>'+$('#annotation_suggestions_lst li.selected .morph_suggestion' ).text()+'</morph></info>');
    };

    function list_normlz_suggestions(suggestions_lst) { //actually suggestions_lst now is one word from <nrm> tag except for normalizations from manual list
        lst_container_tag = $('#normalization_suggestions_lst');
        for (var i in suggestions_lst){
            var tag = $('<li>'+suggestions_lst[i]+'</li>')
            lst_container_tag.append(tag);
            if (i == 0) {
                tag.addClass("selected");
                $('#normalization_input').val(suggestions_lst[i]);
            };
        };
        //var tag = $('<li>'+suggestions_lst+'</li>')
        //lst_container_tag.append(tag);
        //tag.addClass("selected");
        //$('#normalization_input').val(suggestions_lst);
        $('#normalization_suggestions_lst li').click(function(e) {
            $(this).addClass("selected").siblings().removeClass("selected");
            $('#normalization_input').val($(this).text())
        });
    };

    /* LIST ANNOTATION SUGGESTIONS (and add to DOM, if only one) */

    function list_annot_suggestions(suggestions_lst) {
        lst_container_tag = $('#annotation_suggestions_lst');
        lst_container_tag.empty();
        for (var i in suggestions_lst){
            var tag = $('<li><span class="lemma_suggestion">'+suggestions_lst[i][0]+'</span> <span class="morph_suggestion">'+suggestions_lst[i][1]+'</span></li>')
            lst_container_tag.append(tag);
            wb_annotation_mode(); // manual annotation mode in all  cases
            if (i == 0) {
                tag.addClass("selected");
                populate_annotation_form(tag);
            }
            else if (i > 0) {
                // Manual annotation mode when more then one option
                //wb_annotation_mode();
            };
        };
        /* Auto annotation behaviour when one option*/
        /*
        if (i==0) {
            set_annotation();
        };*/

        $('#annotation_suggestions_lst li').click(function(e) {
            $(this).addClass("selected").siblings().removeClass("selected");
            populate_annotation_form($(this));
        });
    };

    function populate_annotation_form(annot_tag) {
        // reset previous annotation form
        $('.manualAnnotationContainer').removeClass('active');
        $('option').removeAttr('selected');
        $("input.manualAnnotation[type='checkbox']").prop('checked', false);

        // parts of current tag
        var this_form = $('#normalization_input').val();
        var this_annot_info = annot_tag.text().split(' ');
        var lemma = this_annot_info.slice(0, -1).join(' ');
        var tags = this_annot_info[this_annot_info.length - 1].split('-');

        // adding lemma
        $('.manualAnnotation#lemma_input').val(lemma).parent().addClass('active');
        $('.manualAnnotation#form_input').val(this_form).parent().addClass('active');

//        $('option#'+tags[0]).prop('selected', true)
//        $('option#'+tags[0]).parent().parent().addClass('active');

        $.each(tags, function(i, el){
            // for compulsory `select` objects
            $('#'+el).prop('selected', true)
            $('#'+el).parent().parent().addClass('active');

            // for checkboxes
            $('[name="'+el+'"]').prop('checked', true)
            $('[name="'+el+'"]').parent().parent().addClass('active');
        });

        activate_annotation_form_fields();

        $('select.manualAnnotation').change(function(e){
            activate_annotation_form_fields();
        });
    };

    function activate_annotation_form_fields() {
        // separate function `activate_annotation_form_fields` is needed
        // because it's called when content of select.manualAnnotation changes
        activate_annotation_options();
        activate_annotation_checkboxes();
    };

    function get_order_by_tag(pos, tagsDict) {
        var orderConfig = $('#manual_annotation').data('order')[pos];
        var configKeys = Object.keys(orderConfig).map(key => key.split(','));
        var tagKeyset = new Set(Object.values(tagsDict));

        var orderKey = 'default';
        for (var a of configKeys) {
            var diff = a.filter(x => !tagKeyset.has(x));
            if (diff.length == 0) {
                orderKey = a.join(',');
                break;
            }
        }
        return orderConfig[orderKey];
    }

    function activate_annotation_options() {
        /* SELECT OPTIONS */
        var tags_dict = {};
        var options_selector = ".manualAnnotationContainer.active select.manualAnnotation option:selected"
        $(options_selector).each(function(i, obj) {
            tags_dict[$(this).parent().attr('id')] = $(this).val();
        });
        var order = get_order_by_tag(tags_dict['part of speech'], tags_dict);
        order.unshift('part of speech');

        $('select.manualAnnotation').each(function() {
            var select_id = $(this).attr('id');
            var container = $(this).parent();
            var blank_option = $(this).find('option#blank');
            if (order.includes(select_id)) {
                container.addClass('active');
                container.attr('idx', order[select_id]);
            } else {
                container.removeClass('active');
                container.removeAttr('idx');
                blank_option.prop('selected', true);
            };
        });

        sort_annotation_options();
    };

    function sort_annotation_options(){
        var annot_form = '#manual_annotation form';
        $(annot_form)
            .children('.active[idx]')
            .sort((a,b) => parseInt($(a).attr("idx")) - parseInt($(b).attr("idx")))
            .appendTo(annot_form);
    }

    function activate_annotation_checkboxes() {
        /* CHECKBOXES */
        $.each($("input.manualAnnotation[type='checkbox']"), function(i){
            var match = 1;

            $.each($(this).data('dep'), function(i, tag){
                var parts = tag.split('.');
                var is_tag_selected = parts.every(part => $('#' + part).is(':checked'));
                if (tag == 'ALLFORMS') {
                    match = 1;
                    return false;

                } else if ( !is_tag_selected ) {
                    match = -1;
                    return false;
                }
            });

            update_annotation_field_status($(this), match);
        });
    };

    function update_annotation_field_status(field, display_idx) {
        if ( display_idx > -1 ) {
            field.parents('.manualAnnotationContainer').addClass('active');
            field.parents('.manualAnnotationContainer').attr('idx', display_idx);
        }
        else {
            field.parents('.manualAnnotationContainer').removeClass('active');
            field.parents('.manualAnnotationContainer').removeAttr('idx');
        };
    };

    /* TEXT MEASURMENTS */

    function getTextWidth(tag) {
        // re-use canvas object for better performance
        var text = tag.text()
        var canvas = getTextWidth.canvas || (getTextWidth.canvas = document.createElement("canvas"));
        var context = canvas.getContext("2d");
        context.font = tag.css('font');
        var metrics = context.measureText(text);
        return metrics.width;
    };

    /* FIND NEXT IN DOM */

    function nextInDOM(_selector, _subject) {
        var next = getNext(_subject);
        while(next != null && next.length != 0) {
            var found = searchFor(_selector, next);
            if(found != null) return found;
            next = getNext(next);
        }
        return null;
    };
    function getNext(_subject) {
        if(_subject.next().length > 0) return _subject.next();
        if(_subject.parent().length > 0) return getNext(_subject.parent());
        return null;
    };
    function searchFor(_selector, _subject) {
        if(_subject.is(_selector)) return _subject;
        else {
            var found = null;
            _subject.children().each(function() {
                found = searchFor(_selector, $(this));
                if(found != null) return false;
            });
            return found;
        }
        return null; // will/should never get here
    };

    /* ANNOTATION OPTIONS TO STRING */

    function annot_to_str() {
        var tags_final_lst = []
        $.each($(".active select"), function(i){
            tags_final_lst.push($(this).val());
        });
        $.each($(".active label input:checked"), function(i){
            tags_final_lst.push($(this).val());
        });
        return tags_final_lst.join("-");
    };

    /* ANNOTATION TO DOM: FINAL */

    function set_annotation (norm_tag, lemma_tag, morph_tag, mode) {

        /* adding normalization, lemma and morphology tags to DOM */

        $('trt.focused').parent().children('nrm, lemma, morph').remove();

        $('trt.focused').parent().prepend(morph_tag);
        $('trt.focused').parent().prepend(lemma_tag);
        $('trt.focused').parent().prepend(norm_tag);

        /* adjusting spacing*/
        var len_transcript = getTextWidth($('.focused'));
        var len_morph = getTextWidth(morph_tag);
        var len_norm = getTextWidth(norm_tag);
        var len_lemma = getTextWidth(lemma_tag);
        if (len_morph > len_transcript && len_morph > len_norm && len_morph > len_lemma) {
            $('trt.focused').css('margin-right', len_morph - len_transcript);
        }
        else if (len_norm > len_morph && len_norm > len_transcript && len_norm > len_lemma) {
            $('.focused').css('margin-right', len_norm - len_transcript)
        }
        else if (len_lemma > len_morph && len_lemma > len_transcript && len_lemma > len_norm) {
            $('.focused').css('margin-right', len_lemma - len_transcript)
        }
        else {
            $('trt.focused').removeAttr('style');
            };
        $('trt.focused').closest('.annot_wrapper').addClass('changed');
        /* continuing to next token*/
        setTimeout(function () {
            var next = nextInDOM('trt', $('trt.focused'));
            if (next) {activate_trt(next, search=check_search_mode())};
        }, 0)
    }

    /* ADJUST SPACING FOR DOM ON INITIAL LOAD */
    function adjust_DOM_spacing() {
        $('token').each(function( index ) {
            if ( $(this).children('morph').length ) {
                var len_transcript = getTextWidth( $(this).children('trt') );
                var len_morph = getTextWidth( $(this).children('morph') );
                var len_norm = getTextWidth( $(this).children('nrm') );
                var len_lemma = getTextWidth( $(this).children('lemma') );
                if (len_morph > len_transcript && len_morph > len_norm && len_morph > len_lemma) {
                    $(this).css('margin-right', len_morph - len_transcript);
                }
                else if (len_norm > len_morph && len_norm > len_transcript && len_norm > len_lemma) {
                    $(this).children('trt').eq(0).css('margin-right', len_norm - len_transcript)
                }
                else if (len_lemma > len_morph && len_lemma > len_transcript && len_lemma > len_norm) {
                    $(this).children('trt').eq(0).css('margin-right', len_lemma - len_transcript)
                }
            }
        });
    }

    /* PLAY SOUND */
    function audiofragment_click(audio_fragment) {
        var active_button = audio_fragment.find(">:first-child");
        if (!active_button.hasClass('fa-play')){
                return false;
        }
        active_button.removeClass('fa-play').addClass('fa-spinner off');
        var starttime = audio_fragment.attr('starttime');
        var duration = audio_fragment.attr('endtime') - starttime;
        var sound = new Howl({
            urls: [$(audio_fragment).parent().prevAll('#elan_audio').attr('src')],
            sprite: {
                segment: [starttime, duration],
            },
            onload: function() {
                active_button.removeClass('fa-spinner off').addClass('fa-play');
            },
            onplay: function() {
                active_button.removeClass('fa-play').addClass('fa-pause');
            },
            onend: function() {
                active_button.removeClass('fa-pause').addClass('fa-play');
            },
        });
        sound.play('segment');
    }

    function check_search_mode() {
        return !!$('#search_form').length;
    }

    function fill_replace_form(token) {
        var elements = [
            ["standartization", "nrm"],
            ["lemma", "lemma"],
            ["annotations", "morph"],
            ["transcription", "trt"]
        ];
        for (var [el_name, tag] of elements) {
            var value = token.find(tag).html();
            $('input[name="from_' + el_name + '"]').val(value);
            $('input[name="to_' + el_name + '"]').val(value);
        }
    }

    function create_replace_query() {
        var query = [];
        var elements = [ // NB: order is important
            ["from_standartization", "nrm"],
            ["from_lemma", "lemma"],
            ["from_annotations", "morph"],
            ["from_transcription", "trt"]
        ];
        for (var [el_name, tag] of elements) {
            var value = $('input[name="' + el_name + '"]').val();
            if (value) { query.push([tag, value]) };
        };
        return query;
    }

    function check_token_by_query(token, query) {
        for (var [tag, value] of query) {
            if (token.find(tag).html() != value) { return false }
        };
        return true;
    }

    function replace(token) {
        token.addClass('changed_by_replace');
        token.closest('.annot_wrapper').addClass('changed');
        var elements = [ // NB: order is important
            ["to_standartization", "nrm"],
            ["to_lemma", "lemma"],
            ["to_annotations", "morph"]
        ];
        for (var [el_name, tag] of elements) {
            var value = $('input[name="' + el_name + '"]').val();
            if (value) {
                token.find(tag).html(value);
            };
        };
    }

    function save_replace_annotations() {
        $('token.changed_by_replace').each( function() {
            var save_annotation_params = {
                'dialect': $(this).closest('.annot').attr('dialect'),
                'trt': $(this).find('trt').html(),
                'nrm': $(this).find('nrm').html(),
                'lemma': $(this).find('lemma').html(),
                'annot': $(this).find('morph').html()
            };
            ajax_request('save_annotation', save_annotation_params, search=true);
       });
       $('token.changed_by_replace').removeClass('changed_by_replace');
    }

    function create_audio() {
        /*AUDIO: LOADING FILE*/
        new Howl({
            urls: [$('#elan_audio').attr('src')],
            onload: function() {
                $(".audiofragment .fa-spinner").removeClass('fa-spinner off').addClass('fa-play');
            }
        });
    }

    function construct_small_page_section(page_num, max_page_num) {
        for (i = 1; i <= max_page_num; i++) {
            var cls = "page_num";
            if (i == 1) { cls += " first"; }
            if (i == page_num) {cls += " current"; }
            if (i == max_page_num) { cls += " last"; }
            $('#page_nums').append('<div class="' + cls + '">' + i + '</div>');
        }
    }

    function construct_large_page_section(page_num, max_page_num) {
        var left = Math.max(1, page_num - 1);
        var right = Math.min(page_num + 1, max_page_num);

        if (page_num != 1) { $('#page_nums').append('<div class="page_num first">1</div>'); }

        if (left - 1 > 2) { $('#page_nums').append('<div class="ellipsis">...</div>'); }
        else if (left - 1 == 2) { $('#page_nums').append('<div class="page_num">2</div>'); }

        if (left - 1 > 0) { $('#page_nums').append('<div class="page_num">' + left + '</div>'); }
        $('#page_nums').append('<div class="page_num current">' + page_num + '</div>');
        if (max_page_num - right > 0) { $('#page_nums').append('<div class="page_num">' + right + '</div>'); }

        if (max_page_num - right > 1) { $('#page_nums').append('<div class="ellipsis">...</div>'); }
        if (max_page_num != page_num) { $('#page_nums').append('<div class="page_num last">' + max_page_num + '</div>'); }

        if (page_num == 1) { $('.page_num.current').addClass('first'); }
        if (page_num == max_page_num) { $('.page_num.current').addClass('last'); }
    }

    function construct_page_section(page_num, max_page_num) {
        $('#page_nums').empty();
        if (max_page_num <= 30) { construct_small_page_section(page_num, max_page_num); }
        else { construct_large_page_section(page_num, max_page_num); }
    }


    /*
    ********************************************************
    DOM EVENTS ONLY:
    ********************************************************
    */

    $(document).ready(function() {

        /* INITIAL ACTIONS ON LOAD */

        /* TYPO.JS SPELLCHECKER TEST
        var dictionary = new Typo("ru_RU", false, false, {dictionaryPath: "/static/js/Typo.js-master/typo/dictionaries"});
        console.log(dictionary.suggest("молако"));
        */

        if (!check_search_mode()) {
            adjust_DOM_spacing();
            create_audio();
        };

        $("#grp-context-navigation").append(
            $("<div id='save_button'><button id='save_to_file' class='fa fa-floppy-o'></div>")
        );

        /*AUDIO: PLAY AT CLICK*/
        $(document).on('click', '.audiofragment', function() {
            audiofragment_click($(this));
        });

        var focused_right_lst = [];
        var focused_left_lst = [];

        /*MERGE CONTROLS*/
        $('#merge_left').click(function(e) {
            console.log('left clicked');
            if (!$('trt.focused#0').length) {
                focused_right_lst = [];
                focused_left_lst = [];
                $('trt.focused').attr('id','0');
            }
            var left_trt_tag = '';
            if (focused_right_lst.length!=0){
                focused_right_lst.pop().removeClass('focused');
            }
            else if (focused_left_lst.length>0) {
                var left_trt_tag = focused_left_lst[focused_left_lst.length-1].parent().prev().find('trt');
            }
            else {
                var left_trt_tag = $('trt.focused#0').parent().prev().find('trt');
            }
            if (left_trt_tag.length){
                left_trt_tag.addClass('focused')
                focused_left_lst.push(left_trt_tag);
            };
            console.log(focused_left_lst);
        });

        $('#merge_right').click(function(e) {
            console.log('right clicked');
            if (!$('trt.focused#0').length) {
                focused_right_lst = [];
                focused_left_lst = [];
                $('trt.focused').attr('id','0');
            }
            var right_trt_tag = '';
            if (focused_left_lst.length!=0){
                focused_left_lst.pop().removeClass('focused');
            }
            else if (focused_right_lst.length>0) {
                var right_trt_tag = focused_right_lst[focused_right_lst.length-1].parent().next().find('trt');
            }
            else {
                var right_trt_tag = $('trt.focused#0').parent().next().find('trt');
            }
            if (right_trt_tag.length){
                right_trt_tag.addClass('focused')
                focused_right_lst.push(right_trt_tag);
            };
            console.log(focused_right_lst);
        });

        $(document).on('click', 'trt', function() {
            var search_mode = check_search_mode();
            activate_trt($(this), search=search_mode);
            if (search_mode) { fill_replace_form($(this).parent()) };

        });

        $('#save_to_file').click(function(e){
            if ($('#save_to_file').hasClass('fa-floppy-o')) {
                $('#save_to_file').removeClass('fa-floppy-o').addClass('fa-spinner off');

                // delay is required for spinner icon to load
                setTimeout(function () {
                    var div_id = '.eaf_display';
                    var is_search_mode = check_search_mode();
                    if (is_search_mode) {
                        div_id = '#search_result';
                        save_replace_annotations();
                    };
                    ajax_request(
                        'save_elan_req',
                        {'html' : '<div>'+$(div_id).html()+'</div>',},
                        search=is_search_mode
                    );
                }, 100)
            }
        });

        $('#add_normalization').click(function(e) {
            /* looking for annotation variants */
            ajax_request(
                'annot_suggest_req',
                {
                    'trt': $('#examined_transcript').text(),
                    'nrm': $('#normalization_input').val(),
                    'dialect': $('trt.focused').closest('.annot').attr('dialect')
                },
                search=check_search_mode()
            );
        });

        $('#add_annotation').click(function(e) {
            /* confirming chosen annotation */
            var norm = $('[title="Form"]').val();
            var lemma = $('[title="Lemma"]').val();
            var morph = annot_to_str();

            var norm_tag = $('<nrm>' + norm + '</nrm>');
            var lemma_tag = $('<lemma>' + lemma + '</lemma>');
            var morph_tag = $('<morph>' + morph + '</morph></info>');

            var save_annotation_params = {
                'trt': $('#examined_transcript').text(),
                'nrm': norm,
                'lemma': lemma,
                'annot': morph
            }
            var search_mode = check_search_mode()
            if (search_mode) {
                save_annotation_params['dialect'] = $('trt.focused').closest('.annot').attr('dialect');
                $('trt.focused').closest('token').removeClass('changed_by_replace');
            };
            ajax_request('save_annotation', save_annotation_params, search=search_mode);

            set_annotation(norm_tag, lemma_tag, morph_tag, 'manual');
        });

        $('#search_button').click(function(e) {
            var formdata = {
                'dialect': $('select[name="dialect"]').val(),
                'transcription': $('input[name="transcription"]').val(),
                'standartization': $('input[name="standartization"]').val(),
                'lemma': $('input[name="lemma"]').val(),
                'annotations': $('input[name="annotations"]').val(),
                'start_page': 1,
                'total_pages': null  // this meand that backend needs to return them
            }
            // todo: insert hiding workbench
            $('#search_button').html('<i class="fa fa-spinner fa-spin"></i>');
            // delay is required for spinner icon to load
            setTimeout(function () { ajax_request('search', formdata, search=true); }, 100);
        });

        $('#search_help_button').click(function(e) {
            $('#search_help').show()
        });

         $('#replace_help_button').click(function(e) {
            $('#replace_help').show()
        });

        $('.close').click(function(e) {
            $(this).parent().hide()
        });

        $(document).on('click', '.page_num', function(e) {
            var page_num = parseInt($(this).text());
            var max_page_num = parseInt($('.page_num.last').text());

            if (max_page_num <= 30) {
                $('.page_num').removeClass('current');
                $(this).addClass('current');
            } else {
                $('#page_nums').empty();
                construct_large_page_section(page_num, max_page_num);
            }

            var formdata = {
                'dialect': $('select[name="dialect"]').val(),
                'transcription': $('input[name="transcription"]').val(),
                'standartization': $('input[name="standartization"]').val(),
                'lemma': $('input[name="lemma"]').val(),
                'annotations': $('input[name="annotations"]').val(),
                'start_page': $(this).text(),
                'total_pages': max_page_num,
                'prev_page_info': JSON.stringify(prev_page_info)
            }
            $('#search_button').html('<i class="fa fa-spinner fa-spin"></i>');
            // delay is required for spinner icon to load
            setTimeout(function () { ajax_request('search', formdata, search=true); }, 100);
        });

        $('#replace_button').click(function(e) {
            $('#replace_button').html('<i class="fa fa-spinner fa-spin"></i>');
            var query = create_replace_query();
            if (query) {
                $("token").each( function() {
                    var is_relevant = check_token_by_query($(this), query);
                    if (is_relevant) { replace($(this)) }
                });
            };
            $('#replace_button').html('Replace');
        });
    });
})(django.jQuery);