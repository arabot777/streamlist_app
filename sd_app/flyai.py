import time
import streamlit as st
import requests
import zipfile
import io
from utils import icon
from streamlit_image_select import image_select
import random

# UI configurations
st.set_page_config(
    page_title="Replicate Image Generator", page_icon=":bridge_at_night:", layout="wide"
)
icon.show_icon(":bird:")
st.markdown("# :rainbow[FlyAI Image Generator]")

CHECKPOINTS_API_URL = "http://43.134.78.67:30000/"
# 用户名和密码的默认值
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "123@456"

# Placeholders for images and gallery
generated_images_placeholder = st.empty()
gallery_placeholder = st.empty()


def login_page():
    with st.form("login_form"):
        st.title("登录")
        username = st.text_input("用户名", value="")
        password = st.text_input("密码", value="", type="password")
        submit = st.form_submit_button("登录")

        if submit:
            if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
                st.success("登录成功！")
                # 更新会话状态为已登录
                st.session_state.logged_in = True
                st.rerun()  # 重新运行脚本以显示主页面
            else:
                st.error("用户名或密码错误，请重新输入。")


def fetch_checkpoints(api_url: str) -> list:
    """
    Fetch checkpoints from the backend API.

    Args:
        api_url (str): The URL of the backend API to fetch checkpoints from.

    Returns:
        list: A list of checkpoints.
    """
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        # return data.get("checkpoints", [])
        return {
            item["name"]: item["model_version_uuid"]
            for item in data.get("data", []).get("item", [])
        }
    except requests.RequestException as e:
        st.error(f"Failed to fetch checkpoints: {e}")
        return []


def fetch_sampler(api_url: str) -> list:
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        return data.get("data", []).get("item", [])
    except requests.RequestException as e:
        st.error(f"Failed to fetch sampler: {e}")
        return []


def configure_sidebar() -> None:
    """
    Setup and display the sidebar elements.

    This function configures the sidebar of the Streamlit application,
    including the form for user inputs and the resources section.
    """

    checkpoints = fetch_checkpoints(
        CHECKPOINTS_API_URL + "/api/v1/model/version/list?type=CHECKPOINT"
    )

    simplerlist = fetch_sampler(CHECKPOINTS_API_URL + "/api/v1/sampler/list")

    with st.sidebar:
        with st.form("my_form"):
            st.info("**Yo fam! Start here ↓**", icon="👋🏾")
            with st.expander(":rainbow[**Refine your output here**]"):
                checkpoint_name = st.selectbox("基础模型", list(checkpoints.keys()))
                checkPointId = checkpoints.get(checkpoint_name)
                # Advanced Settings (for the curious minds!)
                clipSkip = st.slider(
                    "clipSkip跳过层数", value=2, min_value=1, max_value=12
                )
                imgCount = st.slider("图片数量", value=1, min_value=1, max_value=4)
                width = st.number_input("图片宽度", value=1024)
                height = st.number_input("图片高度", value=1024)

                scheduler = st.selectbox("采样算法(Sampler)", simplerlist)
                steps = st.slider("迭代步数", value=20, min_value=1, max_value=60)
                cfgScale = st.slider(
                    "引导词系数(CFG scale)",
                    value=7.0,
                    min_value=0.0,
                    max_value=30.0,
                    step=0.1,
                )
                seed = st.number_input(
                    "随机种子(Seed)",
                    value=random.randint(1, 10000),
                    min_value=-1,
                    step=1,
                    format="%d",
                )
                if seed == 0:
                    st.error("随机种子不能为0，请输入其他值。")
            prompt = st.text_area(
                ":orange[**Enter prompt: start typing, Shakespeare ✍🏾**]",
                value="An astronaut riding a rainbow unicorn, cinematic, dramatic",
            )
            negative_prompt = st.text_area(
                ":orange[**Party poopers you don't want in image? 🙅🏽‍♂️**]",
                value="the absolute worst quality, distorted features",
                help="This is a negative prompt, basically type what you don't want to see in the generated image",
            )

            # The Big Red "Submit" Button!
            submitted = st.form_submit_button(
                "Submit", type="primary", use_container_width=True
            )

        # Credits and resources
        st.divider()

        return (
            submitted,
            width,
            height,
            imgCount,
            scheduler,
            steps,
            cfgScale,
            seed,
            prompt,
            negative_prompt,
            checkPointId,
            clipSkip,
        )


def main_page(
    submitted: bool,
    width: int,
    height: int,
    imgCount: int,
    scheduler: str,
    steps: int,
    cfgScale: float,
    seed: int,
    prompt: str,
    negative_prompt: str,
    checkPointId: str,
    clipSkip: int,
) -> None:
    if submitted:
        with st.status(
            "👩🏾‍🍳 Whipping up your words into art...", expanded=True
        ) as status:
            st.write("⚙️ Model initiated")
            st.write("🙆‍♀️ Stand up and strecth in the meantime")
            try:
                with generated_images_placeholder.container():
                    # 调用后端接口以获取任务的 UUID
                    response = requests.post(
                        CHECKPOINTS_API_URL + "/api/v1/sdjob/text2img",
                        json={
                            "checkPointId": checkPointId,
                            "clipSkip": clipSkip,
                            "width": width,
                            "height": height,
                            "imgCount": imgCount,
                            "scheduler": scheduler,
                            "steps": steps,
                            "cfgScale": cfgScale,
                            "seed": seed,
                            "prompt": prompt,
                            "negativePrompt": negative_prompt,
                        },
                    )
                    response.raise_for_status()
                    task_uuid = response.json().get("data").get("jobUuid")
                    # task_uuid = "c7cc7d28-1b18-4faa-9de2-de97b3686a75"
                    st.session_state.task_uuid = task_uuid
                    st.write(f"Task UUID: {task_uuid}")

                    # 轮询后端接口以获取生成的图片
                    all_images = []
                    while True:
                        result_response = requests.get(
                            f"{CHECKPOINTS_API_URL}/api/v1/sdjob/result?jobUuid={task_uuid}"
                        )
                        result_response.raise_for_status()
                        result_data = result_response.json()
                        if result_data.get("data").get("status") == 2:
                            images = (
                                result_data.get("data", [])
                                .get("output", [])
                                .get("images", [])
                            )
                            for image in images:
                                all_images.append(image.get("imageUrl"))
                            break
                        # elif result_data.get("status") == "failed":
                        #     st.error("任务失败，请重试。")
                        #     return
                        time.sleep(1)  # 等待 5 秒后再次轮询

                    result_images = []
                    if all_images:
                        st.toast("Your image has been generated!", icon="😍")
                        st.session_state.generated_image = all_images

                        # Displaying the image
                        for image in st.session_state.generated_image:
                            with st.container():
                                st.image(
                                    image,
                                    caption="Generated Image 🎈",
                                    use_column_width=True,
                                )
                                response = requests.get(image)
                                if response.status_code == 200:
                                    image_data = response.content
                                    result_images.append(image_data)
                                else:
                                    st.error(
                                        f"Failed to fetch image from {image}. Error code: {response.status_code}",
                                        icon="🚨",
                                    )

                        # Create a BytesIO object
                        zip_io = io.BytesIO()

                        # Download option for each image
                        with zipfile.ZipFile(zip_io, "w") as zipf:
                            for i, image_data in enumerate(result_images):
                                zipf.writestr(f"output_file_{i+1}.png", image_data)

                        # Create a download button for the zip file
                        st.download_button(
                            ":red[**Download the Images**]",
                            data=zip_io.getvalue(),
                            file_name="output_files.zip",
                            mime="application/zip",
                            use_container_width=True,
                        )
                status.update(
                    label="✅ Images generated!", state="complete", expanded=False
                )
            except Exception as e:
                print(e)
                st.error(f"Encountered an error: {e}", icon="🚨")

    # If not submitted, chill here 🍹
    else:
        pass

    # Gallery display for inspo
    with gallery_placeholder.container():
        response = requests.get(f"{CHECKPOINTS_API_URL}/api/v1/sdjob/list")
        response.raise_for_status()
        data = response.json()

        images = []
        captions = []
        for item in data.get("data"):
            prompt = item.get("input", {}).get("txt2img", "").get("prompt", "")
            image_urls = [
                image.get("imageUrl")
                for image in item.get("output", {}).get("images", [])
            ]
            images.extend(image_urls)
            captions.extend([prompt] * len(image_urls))

        images = images[:10]
        captions = captions[:10]
        img = image_select(
            label="近期生图记录～ 😉",
            images=images,
            captions=captions,
            use_container_width=True,
        )


def main():
    """
    Main function to run the Streamlit application.

    This function initializes the sidebar configuration and the main page layout.
    It retrieves the user inputs from the sidebar, and passes them to the main page function.
    The main page function then generates images based on these inputs.
    """
    (
        submitted,
        width,
        height,
        imgCount,
        scheduler,
        steps,
        cfgScale,
        seed,
        prompt,
        negative_prompt,
        checkPointId,
        clipSkip,
    ) = configure_sidebar()
    main_page(
        submitted,
        width,
        height,
        imgCount,
        scheduler,
        steps,
        cfgScale,
        seed,
        prompt,
        negative_prompt,
        checkPointId,
        clipSkip,
    )


# 检查会话状态中是否有登录状态，如果没有，初始化为 False
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if __name__ == "__main__":
    if st.session_state.logged_in:
        main()
    else:
        login_page()