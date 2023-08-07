function ReplaceTagsWithImages(src) {
    if (src.includes('[')) {
        // replace [tag] with image link to tag.svg, but skip strike counts (such as [3])
        const reg =  /\[([a-zA-Z\-_]+)\]/g
        return src.replace(reg, '<' + 'img src="' + primitives_uri + '$1.svg">');
    }
    return src;
}

function edit_item(item_name) {
    pycmd(
        'edit_item-' +
            data.character +
            '-' +
            item_name 
    );
}

function edit_story(story_id) {
    if ( (story_id == "heisig_story") || (story_id == "heisig_comment")) {
        edit_item(story_id);
    } else {

        if (story_id == "usr_story") {
            set_custom_story();			
        } else {
            selected_koohi_story = data.koohi_stories[parseInt(story_id)];
            // strip away the commentator
            idx = selected_koohi_story.indexOf(':')
            if (idx != -1) {
                idx += 2
                selected_koohi_story = selected_koohi_story.substring(idx)
            }
            pycmd(
            'custom_story-' +
                data.character +
                '-' + selected_koohi_story,
            );		
        }
    }
}

function update_story_section() {
    var container = document.getElementById("stories_container");
    stories = container.stories;
    html_stories = '';

    var hide_non_usr_story = false
	if (settings.only_custom_stories && data.usr_story && (!container.edit_mode))
        hide_non_usr_story = true


    for (idx in stories) {
        story_tuple = stories[idx];
        var story_id = story_tuple[0]
        var story = story_tuple[1]
        if ((story_id == "usr_story") || !hide_non_usr_story) {

            if (container.edit_mode) {
                if ((story_id=="heisig_story") && (story=="")) {
                    story="<b>Add Heisig story</b>";
                }
                if ((story_id=="heisig_comment") && (story=="")) {
                    story="<b>Add Heisig comment</b>";
                }
            }
            html_stories += `<p class="story ${container.edit_mode ? 'editable_title' : ''}" 
                ${container.edit_mode ? 'onClick=edit_story("' + story_id + '") ' : ''}
                story_id=${story_id}">` + story + '</p>';
        }
    }
    $('#stories').html(html_stories);
}	

function create_story_section() {

    var userModifiedHeisigStory = (data.mod_heisig_story !== null) || 
    (data.mod_heisig_comment !== null)
    $('#story_title').html(
        `<span class="editable_title ${userModifiedHeisigStory ? ' -user-modified' : ''}" onclick="toggle_story_editing();">Stories</span>`
    );

    var stories = [];
    if (data.usr_story) {
        stories.push( ['usr_story',data.usr_story.split('\n').join('<br>')]);
    }

    if (data.heisig_story) {
        var heisig_story = data.heisig_story;
        var detagged_heisig_story = ReplaceTagsWithImages(heisig_story)
        stories.push(['heisig_story',detagged_heisig_story]);
    } else {
        stories.push(['heisig_story','']);
    }

    if (data.heisig_comment) {
        var detagged_heisig_comment = ReplaceTagsWithImages(data.heisig_comment)
        stories.push(['heisig_comment',detagged_heisig_comment])
    } else {
        stories.push(['heisig_comment','']);
    }

    koohi_story_id = 0
    for (const ks of data.koohi_stories) {
        stories.push([koohi_story_id.toString(), ks]);
        koohi_story_id += 1;
    }

    story_container = document.getElementById("stories_container")
    story_container.stories = stories
    if (!story_container.hasOwnProperty("edit_mode")) {
        story_container.edit_mode = false
    }

    update_story_section();    
}

function toggle_story_editing(state) {
    var container = document.getElementById("stories_container");

    if (typeof state === 'boolean') {
        container.edit_mode = state;
        update_story_section();
    } else {
        container.edit_mode = !container.edit_mode;
        update_story_section();
    }
    container.className = "stories__container" + (container.edit_mode ? " edit_mode" : "")
}
