function ReplaceTagsWithImages(src, img_uri=primitives_uri) {
    if (src.includes('[')) {
        // replace [tag] with image link to tag.svg, but skip strike counts (such as [3])
        rnd = performance.now()
        const reg =  /\[([a-zA-Z\-_]+)\]/g
        return src.replace(reg, '<' + 'img src="' + img_uri + '$1.svg?' + rnd + '">');
    }
    return src;
}

function display_characters(page_type) {

    if (data.character[0] == '[') {
        let img = ReplaceTagsWithImages(data.character)
        let img_cursive = ReplaceTagsWithImages(data.character, cursive_primitives_uri)
        $('#character_img_1').html(img);
        $('#character_img_2').html(img_cursive);
        $('#character_img_3').html('');
        $('#character_img_4').html('');
    } else {
        if (page_type == "recognition") {
            $('.keyword-kanji').html(data.character);
        } else {
            $('.fontExample').html(data.character);    
        }
    }
}

function is_item_modified(source, item_name) {
    if (source in data.stories) {
        if (data.stories[source]['modified_fields'].includes(item_name)) {
            return true;
        }
    }
    return false;
}

function get_keywords(dataset) {
    let keywords = [];
    let raw_keywords = [];
    if (dataset.usr_keyword) keywords.push(dataset.usr_keyword);
    if (!settings.only_custom_keywords || keywords.length < 1 || page_type == "lookup") {
        if (dataset.usr_primitive_keyword)
            keywords.push(
                '<span class="primitive_keyword">' +
                dataset.usr_primitive_keyword +
                    '</span>',
            );
        //for (let [source,src_keywords] of Object.entries(dataset.stories['keywords'])) {
        for (let source in dataset.stories) {
            let color_class = '';
            if (source != 'h')  {
                if (source=='rrtk' || source=='wk') {
                    // we use 'primitive keyword' class to give a RRTK/WK tag in the upper left corner 
                    // even though the keyword may be just a normal keyword and not a primitive one
                    color_class = 'primitive_keyword '; 
                }
                color_class += 'source_' + source
            }
            var userModifiedKeywords = is_item_modified(source,'keywords');
            for (const pk of dataset.stories[source]['keywords']) {
                let conflict = dataset.stories[source]['conflicting_keywords'].includes(pk) ? 'conflicting_keyword' : '';
                const kw = `<span class="${userModifiedKeywords ? ' -user-modified' : ''}${color_class} ${conflict}">` + pk + `</span>`;
                if (!raw_keywords.includes(pk)) {
                    raw_keywords.push(pk);
                    keywords.push(kw);
                }
            }
            var userModifiedPrimitiveKeywords = is_item_modified(source,'primitive_keywords');
            for (const pk of dataset.stories[source]['primitive_keywords']) {
                let conflict = dataset.stories[source]['conflicting_keywords'].includes(pk) ? 'conflicting_keyword' : '';
                const kw = `<span class="primitive_keyword${userModifiedPrimitiveKeywords ? ' -user-modified' : ''} ${color_class} ${conflict}">` + pk + `</span>`;
                if (!raw_keywords.includes(pk)) {
                    raw_keywords.push(pk);
                    keywords.push(kw);
                }
            }
        }
    }
    return keywords;
}
