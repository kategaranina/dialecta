(function($) {
	var processing_request = false;
	function ajax_request(req_type, req_data, search=false, retry=0) {  // TODO: req_type to different funcs?
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
            data: {'request_type' : req_type, 'request_data' : req_data},
            timeout: 300000,
            error: function(x, t, m) {
                console.log(x, t, m);
                alert('Something went wrong. Please contact developers describing the actions that led to the error.')
                processing_request = false;
                if (req_type == 'save_elan_req') {
                    $('#save_to_file').removeClass('fa-spinner off').addClass('fa-floppy-o');
                };
            },
            success: function(response) {
                result = $.parseJSON(response);  // Get the results sended from ajax to here
                processing_request = false
                if (result.error) { // If the function fails
                    console.log(result.error_text); // Error to log
                } else {
                    if (req_type == 'trt_annot_req') {
                        if (req_data['mode'] == 'manual') {
                            list_normlz_suggestions(result.result)
                        }
                        if (req_data['mode'] == 'auto') {
                            //console.log(result.result);
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
                        $('#search_result').html(result.result);
                        if (result.total_pages!=null) {
                            render_page_nums(result.total_pages);
                            $(".page_num").first().addClass('current');
                        };
                        $('#search_button').html('Search');
                        adjust_DOM_spacing();
                    }
                }
            }
        });
	};

	function render_page_nums(total_pages) {
	    $('#page_nums').empty();
	    for (i = 1; i <= total_pages; i++) {
	        $('#page_nums').append('<div class="page_num">' + i + '</div>')
	    }
	}

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

        var full_ann = annotation.map(x => x[0]+'-'+x[1]).join('/');
        var full_lemma = Array.from(new Set(annotation.map(x => x[0]))).join('/');

		var norm_tag = $('<nrm>'+normalization+'</nrm>');
        var lemma_full_tag = $('<lemma_full style="display:none">'+full_lemma+'</lemma_full>');
		var lemma_tag = $('<lemma>'+annotation[0][0]+'</lemma>');
        var morph_full_tag = $('<morph_full style="display:none">'+full_ann+'</morph_full>');
		var morph_tag = $('<morph>'+annotation[0][1]+'</morph></info>');
		set_annotation(norm_tag, lemma_full_tag, lemma_tag, morph_full_tag, morph_tag, 'auto')

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

		$('.manualAnnotationContainer').removeClass('active');
		$('option').removeAttr('selected');
		$("input.manualAnnotation[type='checkbox']").prop('checked', false);

		$('.manualAnnotation#lemma_input').val(annot_tag.text().split(' ').slice(0,-1).join(' ')).parent().addClass('active');
		$('.manualAnnotation#form_input').val($('#normalization_input').val()).parent().addClass('active');
		var this_annot_info = annot_tag.text().split(' ');
		var annot_lst = this_annot_info[this_annot_info.length - 1].split('-');
		//console.log(annot_lst);

		$('option#'+annot_lst[0]).prop('selected', true)
		$('option#'+annot_lst[0]).parent().parent().addClass('active');

		$.each(annot_lst, function(i, el){
			//console.log(el);
			$('#'+el).prop('selected', true).parent().parent().addClass('active');
			$('[name="'+el+'"]').prop('checked', true).parent().parent().addClass('active');
			});
		activate_annotation_form_fields();

		$('select.manualAnnotation').change(function(e){
			//activate_annotation_options($(this).val());
			activate_annotation_form_fields();
		});
	};

	function activate_annotation_form_fields() {
		activate_annotation_options();
		activate_annotation_checkboxes();
	};

	function activate_annotation_options() {
		/* SELECT OPTIONS */
		$.each($("select.manualAnnotation"), function(i){
			var match = false;
			var option_tag = $(this);
			$.each(option_tag.data('dep'), function(i, dict){
				$.each(dict['tags'], function(i, id){
					if (id=='ALLFORMS') {
						match = true;
						return false;
					};
					match = $('#'+id).prop('selected');
					//console.log(option_tag.html(), $('#'+id).html(), $('#'+id).prop('selected'), );
					if (match==false){return false};
				});
				if (match==true){return false};
			});
			//console.log(match)
			update_annotation_field_status(option_tag, match);
		});
	};

	function activate_annotation_checkboxes() {
		/* CHECKBOXES */
		$.each($("input.manualAnnotation[type='checkbox']"), function(i){
			var match = false;
			$.each($(this).data('dep'), function(i, id){
				if (id=='ALLFORMS') {
					match = true;
					return false;
				}
				match = $('#'+id).prop('selected');
				if (match==true){
					return false;
				}
			});
			update_annotation_field_status($(this), match);
			});
	};

	function update_annotation_field_status(field, match) {
		if (match==true) {
			field.parents('.manualAnnotationContainer').addClass('active');
		}
		else {
			field.parents('.manualAnnotationContainer').removeClass('active');
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

	function set_annotation (norm_tag, lemma_full_tag, lemma_tag, morph_full_tag, morph_tag, mode) {

		/* adding normalization, lemma and morphology tags to DOM */

		$('trt.focused').parent().children('nrm, lemma_full, lemma, morph_full, morph').remove();

		$('trt.focused').parent().prepend(morph_tag);
        $('trt.focused').parent().prepend(morph_full_tag);
		$('trt.focused').parent().prepend(lemma_tag);
        $('trt.focused').parent().prepend(lemma_full_tag);
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
		/* continuing to next token*/
		setTimeout(function () {
            var next = nextInDOM('trt', $('trt.focused'));
		    if (next) {activate_trt(next)};
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
		console.log(active_button)
        if (!active_button.hasClass('fa-play')){
                return false;
        }
        var starttime = audio_fragment.attr('starttime');
        var duration = audio_fragment.attr('endtime') - starttime;
        console.log($('#elan_audio').attr('src'))
        var sound =  new Howl({
            urls: [$('#elan_audio').attr('src')],
            sprite: {
                segment: [starttime, duration],
            },
            onplay: function() {
                //console.log(starttime, duration);
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
        var elements = [ // NB: order is important
            ["to_standartization", "nrm"],
            ["to_lemma", "lemma"],
            ["to_annotations", "morph"]
        ];
        for (var [el_name, tag] of elements) {
            var value = $('input[name="' + el_name + '"]').val();
            if (value) {
                token.find(tag).html(value);
                if (tag == "lemma") {
                    token.find("lemma_full").html(value);
                    var full_value = value + '-' + token.find("morph").html();
                    token.find("morph_full").html(full_value);
                };
                if (tag == "morph") {
                    var full_value = token.find("lemma").html() + '-' + value;
                    token.find("morph_full").html(full_value);
                };
            };
        };
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
            /*AUDIO: LOADING FILE*/
            new Howl({
                urls: [$('#elan_audio').attr('src')],
                onload: function() {
                    $(".audiofragment .fa-spinner").removeClass('fa-spinner off').addClass('fa-play');
                }
            });
        };

        $("#grp-context-navigation").append(
            $("<div id='save_button'><button id='save_to_file' class='fa fa-floppy-o'></div>")
        );

//		/*AUDIO: PLAY AT CLICK*/
//		$('.audiofragment').click(function(e) {
//			audiofragment_click($(this));
//		});

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

				var div_id = '.eaf_display';
				var is_search_mode = check_search_mode();
				if (is_search_mode) {div_id = '#search_result'};
                console.log(div_id)
				ajax_request(
                    'save_elan_req',
                    {'html' : '<div>'+$(div_id).html()+'</div>',},
                    search=is_search_mode
				);
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
            var lemma_full_tag = $('<lemma_full style="display:none">' + lemma + '</lemma_full>');
			var lemma_tag = $('<lemma>' + lemma + '</lemma>');
            var morph_full_tag = $('<morph_full style="display:none">' + lemma + '-' + morph + '</morph_full>');
			var morph_tag = $('<morph>' + morph + '</morph></info>');

            var save_annotation_params = {
                'trt': $('#examined_transcript').text(),
                'nrm': norm,
                'lemma': lemma,
                'annot': morph
            }
            var search_mode = check_search_mode()
            if (search_mode) { save_annotation_params['dialect'] = $('trt.focused').closest('.annot').attr('dialect') };
			ajax_request('save_annotation', save_annotation_params, search=search_mode);

			set_annotation(norm_tag, lemma_full_tag, lemma_tag, morph_full_tag, morph_tag, 'manual');
		});

        $('#search_button').click(function(e) {
            var formdata = {
                'dialect': $('select[name="dialect"]').val(),
                'transcription': $('input[name="transcription"]').val(),
                'standartization': $('input[name="standartization"]').val(),
                'lemma': $('input[name="lemma"]').val(),
                'annotations': $('input[name="annotations"]').val(),
                'start_page': 0,
                'return_total_pages': true
            }
            $('#search_button').html('<i class="fa fa-spinner fa-spin"></i>');
            ajax_request('search', formdata, search=true);
        });

        $(document).on('click', '.page_num', function(e) {
            $('.page_num').removeClass('current');
            $(this).addClass('current');
            var formdata = {
                'dialect': $('select[name="dialect"]').val(),
                'transcription': $('input[name="transcription"]').val(),
                'standartization': $('input[name="standartization"]').val(),
                'lemma': $('input[name="lemma"]').val(),
                'annotations': $('input[name="annotations"]').val(),
                'start_page': $(this).text()
            }
            $('#search_button').html('<i class="fa fa-spinner fa-spin"></i>');
            ajax_request('search', formdata, search=true);
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