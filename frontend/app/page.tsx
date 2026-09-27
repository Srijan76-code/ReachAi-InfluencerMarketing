import { Status, StatusIndicator, StatusLabel } from "@/components/kibo-ui/status";
import { LoaderWithText } from "@/components/LoaderWithText";
import { Loader } from "@/components/ui/loader";
import { RiPulseAiFill } from "@remixicon/react";
import { Loading } from "@/components/ui/loading";
import { cn } from "@/lib/utils";
const page = () => {
  return <div className="min-h-screen mx-auto pt-64 max-w-svh ">
    {/* <LoaderWithText/> */}
    {/* <RiPulseAiFill/> */}
    {/* <Loading animation="lift" size={32} speed={0.5} /> */}
    {/* <div className="flex justify-center items-center mb-4">


    </div>

    <div className="flex w-full h-96 flex-col  gap-4">

      <Status status="online">
        <StatusIndicator />
        <StatusLabel className="text-foreground text-xs">System connected</StatusLabel>
      </Status>
      <Loader variant={"text-shimmer"} text={"Loading...."} />
    </div> */}
    page
  </div>;
};

export default page;
